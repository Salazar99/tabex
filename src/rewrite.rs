use std::{collections::{btree_map::Entry, BTreeMap, BTreeSet}, vec};

use crate::{formula::{Formula, FormulaKind, Interval}, node::Node};

#[cfg(test)]
mod tests;

pub fn merge_globally(input: &Vec<Formula>, time: i32) -> Option<Vec<Formula>> {
    let mut map: BTreeMap<(Formula, Option<i32>), (usize, Interval)> = BTreeMap::new();
    let mut to_remove = BTreeSet::new();

    for (idx, op) in input.iter().enumerate() {
        if let FormulaKind::G { interval, phi, parent_upper } = &op.kind {
            let key = (*phi.clone(), parent_upper.clone());
            match map.entry(key) {
                Entry::Occupied(mut occ) => {
                    let (_, int) = occ.get_mut();
                    if let (Some(interval_u), Some(int_u)) = (interval.shift_left(time), int.shift_left(time)) {
                        if int_u.intersects(&interval_u) || int_u.contiguous(&interval_u) {
                            to_remove.insert(idx);
                            *int = int.union(&interval);
                        }
                    }
                }
                Entry::Vacant(v) => { v.insert((idx, interval.clone())); }
            }
        }
    }

    if to_remove.is_empty() { return None; }
    let mut new_operands = input.clone();
    for el in map {
        let (idx, new_interval) = el.1;
        new_operands[idx] = new_operands[idx].with_interval(new_interval);
    }
    
    new_operands = new_operands.iter().enumerate()
        .filter(|(i, _)| !to_remove.contains(i))
        .map(|(_, f)| f.clone())
        .collect();

    Some(new_operands)
}

pub fn merge_finally(input: &Vec<Formula>, time: i32) -> Option<Vec<Formula>> {
    let mut map: BTreeMap<(Formula, Option<i32>), (usize, Interval)> = BTreeMap::new();
    let mut to_remove = BTreeSet::new();

    for (idx, op) in input.iter().enumerate() {
        if let FormulaKind::F { phi, parent_upper, interval} = &op.kind {
            let key = (*phi.clone(), parent_upper.clone());
            match map.entry(key) {
                Entry::Occupied(mut occ) => {
                    let (i, int) = occ.get_mut();
                    if let (Some(interval_u), Some(int_u)) = (interval.shift_left(time), int.shift_left(time)) {
                        if interval_u.contains(&int_u) {
                            to_remove.insert(idx);
                        } else if int_u.contains(&interval_u) {
                            to_remove.insert(*i); *i = idx; *int = interval.clone();
                        }
                    }
                }
                Entry::Vacant(v) => { v.insert((idx, interval.clone())); }
            }
        }
    }

    if to_remove.is_empty() { return None; }
    Some(input.iter().enumerate().filter(|(i, _)| !to_remove.contains(i)).map(|(_, f)| f.clone()).collect())
}

pub fn rewrite_globally_finally(input: &Vec<Formula>, time: i32) -> Option<Vec<Formula>> {
    let mut new_operands = Vec::new();
    let mut new_nodes = Vec::new();

    for op in input {
        if let FormulaKind::G { interval: g_int, phi, .. } = &op.kind && time + 2 <= g_int.upper 
         && let FormulaKind::F { interval: f_int, .. } = &phi.kind && op.is_active_at(time) {
            let first = op.with_interval(Interval { lower: time + 2, upper: g_int.upper });

            let second = Formula::or(vec![
                phi.with_interval(Interval { lower: time + f_int.lower + 1, upper: time + f_int.upper }),
                Formula::and(vec![
                    phi.with_interval(Interval {lower: time + f_int.lower, upper: time + f_int.lower}),
                    phi.with_interval(Interval {lower: time + f_int.upper + 1, upper: time + f_int.upper + 1})
                ])
            ]);
            new_operands.push(first);
            new_nodes.push(second);
        } else {
            new_operands.push(op.clone());
        }
    }

    if new_nodes.is_empty() {
        return None;
    }

    for node in new_nodes {
        new_operands.push(node);
    }

    Some(new_operands)
}

impl Node {
    pub fn mltl_rewrite(&mut self) {
        self.operands.iter_mut().for_each(|f| {
            *f = f.mltl_rewrite();
        });
    }

    pub fn negative_normal_form_rewrite(&mut self) {
        self.operands.iter_mut().for_each(|f| {
            *f = f.negative_normal_form_rewrite();
        });
    }

    pub fn flatten(&mut self) {
        let mut flattened: Vec<Formula> = Vec::new();
        for f in &self.operands {
            let flat = f.flat_rewrite();
            if let FormulaKind::And(ops) = &flat.kind {
                flattened.extend(ops.iter().cloned());
            } else {
                flattened.push(flat);
            }
        }
        self.operands = flattened;
    }

    pub fn shift_bounds(&mut self) {
        fn get_shift(formula: &Formula) -> Option<i32> {
            match &formula.kind {
                FormulaKind::O(inner) 
                | FormulaKind::Not(inner) => get_shift(inner),
                FormulaKind::And(operands) 
                | FormulaKind::Or(operands) => {
                    operands.iter().map(|op| get_shift(op)).min().unwrap_or(None)
                },
                FormulaKind::Imply { left, right, not_left } => get_shift(left).min(get_shift(right)).min(get_shift(not_left)),
                FormulaKind::G { interval, .. } 
                | FormulaKind::F { interval, .. } 
                | FormulaKind::U { interval, .. }
                | FormulaKind::R { interval, .. } => Some(interval.lower),
                _ => None,
            }
        }
        fn shift_backward(formula: &mut Formula, shift: i32) {
            match &mut formula.kind {
                FormulaKind::And(ops) => ops.iter_mut().for_each(|f| shift_backward(f, shift)),
                FormulaKind::Or(ops) => ops.iter_mut().for_each(|f| shift_backward(f, shift)),
                FormulaKind::Imply { left, right, not_left } => {
                    shift_backward(left, shift);
                    shift_backward(right, shift);
                    shift_backward(not_left, shift);
                },
                FormulaKind::O(i) => shift_backward(i, shift),
                FormulaKind::Not(i) => shift_backward(i, shift),
                FormulaKind::G { interval, .. } | FormulaKind::F { interval, .. } | FormulaKind::U { interval, .. } | FormulaKind::R { interval, .. } => {
                    interval.lower -= shift;
                    interval.upper -= shift;
                },
                _ => {}
            }
        }
        fn inner_rewrite(formula: &mut Formula) {
            match &mut formula.kind {
                FormulaKind::And(ops) => ops.iter_mut().for_each(|f| inner_rewrite(f)),
                FormulaKind::Or(ops) => ops.iter_mut().for_each(|f| inner_rewrite(f)),
                FormulaKind::O(i) | FormulaKind::Not(i) => inner_rewrite(i),
                FormulaKind::Imply { left, right, not_left } => {
                    inner_rewrite(left); 
                    inner_rewrite(right);
                    inner_rewrite(not_left);
                },
                FormulaKind::G { phi, interval, .. } | FormulaKind::F { phi, interval, .. } => {
                    inner_rewrite(phi);
                    if let Some(shift) = get_shift(phi) {
                        shift_backward(phi, shift);
                        interval.lower += shift;
                        interval.upper += shift;
                    }
                },
                FormulaKind::U { interval, left, right, .. } | FormulaKind::R { interval, left, right, .. } => {
                    inner_rewrite(left);
                    inner_rewrite(right);
                    if let Some(shift) = get_shift(left).min(get_shift(right)) {
                        shift_backward(left, shift);
                        shift_backward(right, shift);
                        interval.lower += shift;
                        interval.upper += shift;
                    }
                }
                _ => {}
            }
        }
        self.operands.iter_mut().for_each(|f| {
            inner_rewrite(f);
        });
    }

    pub fn rewrite_chain(&self) -> Option<Vec<Node>> {
        let mut current = self.operands.clone();
        let mut changed = false;

        loop {
            if let Some(res) = merge_globally(&current, self.current_time) {
                current = res;
                changed = true;
            } else if let Some(res) = merge_finally(&current, self.current_time) {
                current = res;
                changed = true;
            } else if let Some(res) = rewrite_globally_finally(&current, self.current_time) {
                current = res;
                changed = true;
            } else {
                break;
            }
        }

        if changed {
            let mut new_node = self.clone();
            new_node.operands = current;
            Some(vec![new_node])
        } else {
            None
        }
    }
}

impl Formula {
    pub fn negative_normal_form_rewrite(&self) -> Formula {
        match &self.kind {
            FormulaKind::Not(inner) => {
                match &inner.kind {
                    FormulaKind::Not(i) => i.negative_normal_form_rewrite(),
                    FormulaKind::And(ops) => Formula::or(ops.iter().map(|f| Formula::not(f.clone()).negative_normal_form_rewrite()).collect()),
                    FormulaKind::Or(ops) => Formula::and(ops.iter().map(|f| Formula::not(f.clone()).negative_normal_form_rewrite()).collect()),
                    FormulaKind::Imply { left, right, .. } => Formula::and(vec![*left.clone(), Formula::not(*right.clone()).negative_normal_form_rewrite()]),
                    FormulaKind::G { phi, interval, parent_upper } => 
                        Formula::f(interval.clone(), *parent_upper, Formula::not(*phi.clone()).negative_normal_form_rewrite()),
                    FormulaKind::F { phi, interval, parent_upper } => 
                        Formula::g(interval.clone(), *parent_upper, Formula::not(*phi.clone()).negative_normal_form_rewrite()),
                    FormulaKind::U { interval, left, right, parent_upper } => 
                        Formula::r(interval.clone(), *parent_upper, Formula::not(*left.clone()).negative_normal_form_rewrite(), Formula::not(*right.clone()).negative_normal_form_rewrite()),
                    FormulaKind::R { interval, left, right, parent_upper } => 
                        Formula::u(Interval { lower: 0, upper: interval.lower }, *parent_upper, Formula::not(*left.clone()).negative_normal_form_rewrite(), Formula::not(*right.clone()).negative_normal_form_rewrite()),
                    FormulaKind::O(i) => Formula::o(Formula::not(*i.clone()).negative_normal_form_rewrite()),
                    _ => self.clone()
                }
            }
            FormulaKind::And(ops) | FormulaKind::Or(ops) => {
                self.with_operands(ops.iter().map(|f| f.negative_normal_form_rewrite()).collect())
            }
            FormulaKind::Imply { left, right, not_left } => {
                self.with_implication(left.negative_normal_form_rewrite(), right.negative_normal_form_rewrite(), not_left.negative_normal_form_rewrite())
            }
            FormulaKind::G { phi, .. } | FormulaKind::F { phi, .. } => {
                self.with_operand(phi.negative_normal_form_rewrite())
            }
            FormulaKind::U { left, right, .. } | FormulaKind::R { left, right, .. } => {
                self.with_operand_couple(left.negative_normal_form_rewrite(), right.negative_normal_form_rewrite())
            }
            _ => self.clone()
        }
    }

    pub fn mltl_rewrite(&self) -> Formula {
        debug_assert!(self.is_negation_normal_form(), "Normalization failed: formula not in NNF");

        match &self.kind {
            FormulaKind::And(ops) | FormulaKind::Or(ops) => 
                self.with_operands(ops.iter().map(|f| f.mltl_rewrite()).collect()),
            FormulaKind::G { phi, .. } | FormulaKind::F { phi, .. } => {
                self.with_operand(phi.mltl_rewrite())
            }
            FormulaKind::Imply { left, right, not_left } => 
                self.with_implication(left.mltl_rewrite(), right.mltl_rewrite(), not_left.mltl_rewrite()),
            FormulaKind::U { interval, left, right, .. } => {
                let g_part = Formula::g(Interval { lower: 0, upper: interval.lower }, None, left.mltl_rewrite());
                Formula::and(vec![g_part, self.with_operand_couple(left.mltl_rewrite(), right.mltl_rewrite())])
            }
            FormulaKind::R { interval, left, right, .. } => {
                let f_part = Formula::f(Interval { lower: 0, upper: interval.lower }, None, left.mltl_rewrite());
                Formula::or(vec![f_part, self.with_operand_couple(left.mltl_rewrite(), right.mltl_rewrite())])
            }
            _ => self.clone()
        }
    }

    pub fn flat_rewrite(&self) -> Formula {
        debug_assert!(self.is_negation_normal_form(),"Normalization failed: formula not in NNF");

        match &self.kind {
            FormulaKind::And(ops) => {
                self.with_operands(
                    ops.iter().map(|op| op.flat_rewrite()).flat_map(|flat_op| {
                        if let FormulaKind::And(inner_ops) = &flat_op.kind { 
                            inner_ops.clone() 
                        } else { 
                            vec![flat_op] 
                        }
                    }).collect()
                )
            }
            FormulaKind::Or(ops) => {
                self.with_operands(
                    ops.iter().map(|op| op.flat_rewrite()).flat_map(|flat_op| {
                        if let FormulaKind::Or(inner_ops) = &flat_op.kind { 
                            inner_ops.clone() 
                        } else { 
                            vec![flat_op] 
                        }
                    }).collect()
                )
            }
            FormulaKind::G { phi, .. } | FormulaKind::F { phi, .. } => {
                self.with_operand(phi.flat_rewrite())
            }
            FormulaKind::U { left, right, .. } | FormulaKind::R { left, right, .. } => {
                self.with_operand_couple(left.flat_rewrite(), right.flat_rewrite())
            }
            FormulaKind::Imply { left, right, not_left } => {
                self.with_implication(left.flat_rewrite(), right.flat_rewrite(), not_left.flat_rewrite())
            }
            _ => self.clone()
        }
    }
}