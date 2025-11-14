use std::collections::BTreeSet;
use std::vec;

use crate::formula::{Formula, Interval};
use crate::sat::tableau::Tableau;
use crate::sat::tableau::node::{Node, NodeFormula};

#[cfg(test)]
mod tests;

impl Tableau {
    #[must_use]
    pub fn decompose(&self, node: &Node) -> Option<Vec<Node>> {
        if self.tableau_options.formula_optimizations
            && let Some(res) = node.rewrite_chain()
        {
            return Some(res);
        }

        if let Some(res) = self.decompose_and(node) {
            return Some(res);
        }

        if let Some(res) = self.decompose_g(node) {
            return Some(res);
        }

        for (i, operand) in node.operands.iter().enumerate() {
            match &operand.kind {
                Formula::Or(_) => {
                    return Some(self.decompose_or_at(node, i));
                }
                Formula::Imply { .. } => {
                    return Some(self.decompose_imply_at(node, i));
                }
                _ => {}
            }
        }

        for (i, operand) in node.operands.iter().enumerate() {
            match &operand.kind {
                Formula::F { .. } if !operand.marked && operand.is_active_at(node.current_time) => {
                    return Some(self.decompose_f_at(node, i));
                }
                Formula::U { .. } if !operand.marked && operand.is_active_at(node.current_time) => {
                    return Some(self.decompose_u_at(node, i));
                }
                Formula::R { .. } if !operand.marked && operand.is_active_at(node.current_time) => {
                    return Some(self.decompose_r_at(node, i));
                }
                _ => {}
            }
        }

        self.decompose_jump(node)
    }

    #[must_use]
    pub fn decompose_and(&self, node: &Node) -> Option<Vec<Node>> {
        let mut changed = false;
        let flattened_operands: Vec<NodeFormula> = node
            .operands
            .iter()
            .flat_map(|nf| match &nf.kind {
                Formula::And(inner) => {
                    changed = true;
                    inner
                        .iter()
                        .map(|f| nf.clone().with_kind(f.clone()))
                        .collect()
                }
                _ => vec![nf.clone()],
            })
            .collect();

        changed.then(|| {
            vec![Node {
                operands: flattened_operands,
                ..node.clone()
            }]
        })
    }

    #[must_use]
    pub fn decompose_g(&self, node: &Node) -> Option<Vec<Node>> {
        let mut changed = false;
        let flattened_operands: Vec<NodeFormula> = node
            .operands
            .iter()
            .flat_map(|f| match &f.kind {
                Formula::G { interval, phi, .. }
                    if f.is_active_at(node.current_time) && !f.marked =>
                {
                    changed = true;
                    if node.current_time < interval.upper {
                        vec![
                            f.clone().with_marked(true),
                            phi.temporal_expansion(node.current_time, Some(interval)),
                        ]
                    } else {
                        vec![phi.temporal_expansion(node.current_time, Some(interval))]
                    }
                }
                _ => vec![f.clone()],
            })
            .collect();

        changed.then(|| {
            vec![Node {
                operands: flattened_operands,
                ..node.clone()
            }]
        })
    }

    #[must_use]
    pub fn decompose_or_at(&self, node: &Node, i: usize) -> Vec<Node> {
        let Formula::Or(or_operands) = &node.operands[i].kind else {
            panic!("decompose_or_at called on non-Or formula at index {i}");
        };

        or_operands
            .iter()
            .map(|or_operand| {
                let mut new_operands = node.operands.clone();
                new_operands[i] = node.operands[i].clone().with_kind(or_operand.clone());
                Node {
                    operands: new_operands,
                    ..node.clone()
                }
            })
            .collect()
    }

    #[must_use]
    pub fn decompose_imply_at(&self, node: &Node, i: usize) -> Vec<Node> {
        let Formula::Imply {
            left,
            right,
            not_left,
        } = &node.operands[i].kind
        else {
            panic!("decompose_imply_at called on non-Imply formula at index {i}");
        };

        let mut new_node1 = node.clone();
        new_node1.operands[i] = node.operands[i].clone().with_kind((**not_left).clone());

        let mut new_node2 = node.clone();
        new_node2.operands[i] = node.operands[i].clone().with_kind((**right).clone());
        if self.tableau_options.formula_optimizations {
            new_node2
                .operands
                .insert(i, node.operands[i].clone().with_kind((**left).clone()));
        }

        vec![new_node1, new_node2]
    }

    #[must_use]
    pub fn decompose_f_at(&self, node: &Node, i: usize) -> Vec<Node> {
        let f_formula = &node.operands[i];

        let Formula::F { phi, interval, .. } = &f_formula.kind else {
            panic!("decompose_f_at called on non-F formula at index {i}");
        };

        debug_assert!(
            node.operands[i].is_active_at(node.current_time),
            "decompose_f_at called on F formula that is not active at current time {}",
            node.current_time
        );

        debug_assert!(
            !node.operands[i].marked,
            "decompose_f_at called on F formula that is already marked at current time {}",
            node.current_time
        );

        // Node where F is satisfied (p)
        let mut new_node1 = node.clone();
        new_node1.operands[i] = phi.temporal_expansion(node.current_time, None);

        // Node in which F is not satisfied (OF)
        if node.current_time < interval.upper {
            let mut new_node2 = node.clone();
            new_node2.operands[i] = f_formula.clone().with_marked(true);

            vec![new_node1, new_node2]
        } else {
            vec![new_node1]
        }
    }

    #[must_use]
    pub fn decompose_u_at(&self, node: &Node, i: usize) -> Vec<Node> {
        let u_formula = &node.operands[i];

        let Formula::U {
            left,
            right,
            interval,
            ..
        } = &u_formula.kind
        else {
            panic!("decompose_u_at called on non-U formula at index {i}");
        };

        debug_assert!(
            node.operands[i].is_active_at(node.current_time),
            "decompose_u_at called on U formula that is not active at current time {}",
            node.current_time
        );

        debug_assert!(
            !node.operands[i].marked,
            "decompose_u_at called on U formula that is already marked at current time {}",
            node.current_time
        );

        // Node where U is satisfied (q)
        let mut new_node1 = node.clone();
        new_node1.operands[i] = right.temporal_expansion(node.current_time, None);

        if node.current_time < interval.upper {
            // Node in which U is not satisfied (p, OU)
            let mut new_node2 = node.clone();
            new_node2.operands[i] = left.temporal_expansion(node.current_time, Some(interval));
            new_node2.operands.push(u_formula.clone().with_marked(true));

            return vec![new_node1, new_node2];
        }
        vec![new_node1]
    }

    #[must_use]
    pub fn decompose_r_at(&self, node: &Node, i: usize) -> Vec<Node> {
        let r_formula = &node.operands[i];

        let Formula::R {
            interval,
            left,
            right,
            ..
        } = &r_formula.kind
        else {
            panic!("decompose_r_at called on non-R formula at index {i}");
        };

        debug_assert!(
            node.operands[i].is_active_at(node.current_time),
            "decompose_r_at called on R formula that is not active at current time {}",
            node.current_time
        );

        debug_assert!(
            !node.operands[i].marked,
            "decompose_r_at called on R formula that is already marked at current time {}",
            node.current_time
        );

        // Node where R is satisfied now
        let new_node1 = if self.options.mltl {
            // MLTL decomposition (p, q)
            let mut node: Node = node.clone();
            node.operands[i] = left.temporal_expansion(node.current_time, None);
            node.operands
                .insert(i, right.temporal_expansion(node.current_time, None));
            node
        } else {
            // STL decomposition (p)
            let mut node: Node = node.clone();
            node.operands[i] = left.temporal_expansion(node.current_time, None);
            node
        };

        // Node in which R is not satisfied now (q, OR)
        let mut new_node2 = node.clone();
        new_node2.operands[i] = right.temporal_expansion(node.current_time, Some(interval));
        if node.current_time < interval.upper {
            new_node2.operands.push(r_formula.clone().with_marked(true));
        }

        vec![new_node1, new_node2]
    }

    #[must_use]
    pub fn decompose_jump(&self, node: &Node) -> Option<Vec<Node>> {
        fn retime_poised(formula: &NodeFormula, current_time: i32) -> Option<NodeFormula> {
            let interval = formula.kind.get_interval()?;
            if current_time >= interval.upper {
                return None;
            }

            Some(formula.clone().with_marked(false))
        }

        fn sorted_time_instants(node: &Node) -> BTreeSet<i32> {
            fn top_level_interval(formula: &NodeFormula, current_time: i32) -> Option<Vec<i32>> {
                match &formula.kind.get_interval() {
                    Some(interval) if !formula.is_parent_active_at(current_time) => {
                        Some(vec![interval.lower, interval.upper])
                    }
                    _ => None,
                }
            }
            node.operands
                .iter()
                .filter_map(|f| top_level_interval(f, node.current_time))
                .flatten()
                .collect()
        }

        pub fn get_max_upper(formula: &Formula) -> Option<i32> {
            match &formula {
                Formula::And(operands) | Formula::Or(operands) => {
                    operands.iter().map(get_max_upper).max().unwrap_or(None)
                }
                Formula::Imply { left, right, .. } => get_max_upper(left).max(get_max_upper(right)),
                _ => formula.upper_bound(),
            }
        }

        // Verify jump rule condition
        let step = !self.tableau_options.jump_rule_enabled
            || node
                .operands
                .iter()
                .filter(|f| f.marked && !f.is_parent_active_at(node.current_time))
                .any(|f| {
                    f.kind.upper_bound() == Some(node.current_time)
                        || match &f.kind {
                            Formula::G { phi, interval, .. }
                            | Formula::U {
                                left: phi,
                                interval,
                                ..
                            }
                            | Formula::R {
                                right: phi,
                                interval,
                                ..
                            } => match get_max_upper(phi) {
                                None => false,
                                Some(max_upper) => node.current_time < interval.lower + max_upper,
                            },
                            _ => false,
                        }
                })
            || (node.operands.iter().any(|f| {
                matches!(f.kind, Formula::Prop(_) | Formula::Not(_))
                    && !f.is_parent_active_at(node.current_time)
            }) && node.operands.iter().any(|f| {
                matches!(
                    f.kind,
                    Formula::F { .. } | Formula::U { .. } | Formula::R { .. }
                ) && f.marked
            }));

        // Select jump length
        let jump = if step {
            1
        } else if let Some(target_time) = sorted_time_instants(node)
            .into_iter()
            .find(|&t| t > node.current_time)
        {
            target_time - node.current_time
        } else {
            return None;
        };

        // Retain only temporal operators, and retimed O formulas
        let new_operands: Vec<NodeFormula> = node
            .operands
            .iter()
            .filter_map(|op| match &op.kind.get_interval() {
                Some(_) => retime_poised(op, node.current_time),
                _ => None,
            })
            .collect();

        // Construct return value
        if new_operands.is_empty() {
            return None;
        }

        let mut new_node = node.clone();
        new_node.operands = new_operands;
        new_node.current_time += jump;

        if self.tableau_options.simple_first {
            let simple_operands: Vec<NodeFormula> = new_node
                .operands
                .iter()
                .filter(|f| !f.kind.is_complex_temporal_operator())
                .cloned()
                .collect();
            if !simple_operands.is_empty() && simple_operands.len() < new_node.operands.len() {
                let mut simple_node = new_node.clone();
                simple_node.operands = simple_operands;
                simple_node.implies = Some(vec![new_node.id]);
                return Some(vec![simple_node, new_node]);
            }
        }
        Some(vec![new_node])
    }
}

impl Formula {
    fn temporal_expansion(
        &self,
        current_time: i32,
        parent_interval: Option<&Interval>,
    ) -> NodeFormula {
        fn inner(formula: &Formula, current_time: i32) -> Formula {
            match formula {
                Formula::Prop(_) | Formula::Not(_) => formula.clone(),
                Formula::F { interval, .. }
                | Formula::G { interval, .. }
                | Formula::U { interval, .. }
                | Formula::R { interval, .. } => {
                    formula.with_interval(interval.shift_right(current_time))
                }
                Formula::And(operands) | Formula::Or(operands) => formula
                    .with_operands(operands.iter().map(|op| inner(op, current_time)).collect()),
                Formula::Imply {
                    left,
                    right,
                    not_left,
                } => formula.with_implication(
                    inner(left, current_time),
                    inner(right, current_time),
                    inner(not_left, current_time),
                ),
            }
        }
        let mut new_node: NodeFormula = inner(self, current_time).into();
        new_node.parent_upper = parent_interval.map(|int| int.upper);
        new_node
    }
}
