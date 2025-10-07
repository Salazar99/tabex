use std::{collections::{btree_map::Entry, BTreeMap, BTreeSet}, vec};

use crate::{formula::{Formula, Interval}, node::Node};

#[cfg(test)]
mod tests;

pub fn merge_globally(input: &Vec<Formula>, time: i32) -> Option<Vec<Formula>> {
    let mut map: BTreeMap<(Formula, Option<i32>), (usize, Interval)> = BTreeMap::new();
    let mut to_remove = BTreeSet::new();

    for (idx, op) in input.iter().enumerate() {
        if let Formula::G { interval, parent_upper, phi } = op {
            match map.entry((*phi.clone(), *parent_upper)) {
                Entry::Occupied(mut occ) => {
                    let (_, int) = occ.get_mut();
                    if let (Some(interval_u), Some(int_u)) = (interval.shift_left(time), int.shift_left(time)) {
                        if int_u.intersects(&interval_u) || int_u.contiguous(&interval_u) {
                            to_remove.insert(idx);
                            *int = int.union(interval);
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
        let (phi, pu) = el.0;
        let (idx, interval) = el.1;
        new_operands[idx] = Formula::G { interval: interval.clone(), parent_upper: pu, phi: Box::new(phi.clone()) };
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
        if let Formula::F { interval, parent_upper, phi } = op {
            match map.entry((*phi.clone(), *parent_upper)) {
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
        if let Formula::G { interval: g_int, phi, parent_upper } = op && time + 2 <= g_int.upper &&
            let Formula::F { interval: f_int, phi: psi, .. } = &**phi && op.active(time) {
                let first = Formula::G { 
                    interval: Interval { lower: time + 2, upper: g_int.upper }, 
                    parent_upper: *parent_upper, phi: phi.clone() 
                };
                let second = Formula::Or(vec![
                    Formula::F { 
                        interval: Interval { lower: time + f_int.lower + 1, upper: time + f_int.upper }, 
                        parent_upper: None, phi: psi.clone() 
                    },
                    Formula::And(vec![
                        Formula::G { 
                            interval: Interval { lower: time + f_int.lower, upper: time + f_int.lower }, 
                            parent_upper: None, phi: psi.clone()
                        },
                        Formula::G { 
                            interval: Interval { lower: time + f_int.upper + 1, upper: time + f_int.upper + 1 }, 
                            parent_upper: None, phi: psi.clone()
                        },
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
    pub fn rewrite_u_r(&mut self) {
        fn inner_rewrite(formula: &Formula) -> Formula {
            match formula {
                Formula::And(ops) => Formula::And(ops.iter().map(|f| inner_rewrite(f)).collect()),
                Formula::Or(ops) => Formula::Or(ops.iter().map(|f| inner_rewrite(f)).collect()),
                Formula::O(i) => Formula::O(Box::new(inner_rewrite(i))),
                Formula::Not(i) => Formula::Not(Box::new(inner_rewrite(i))),
                Formula::G { phi, interval, parent_upper } => Formula::G { phi: Box::new(inner_rewrite(phi)), interval: interval.clone(), parent_upper: parent_upper.clone() },
                Formula::F { phi, interval, parent_upper } => Formula::F { phi: Box::new(inner_rewrite(phi)), interval: interval.clone(), parent_upper: parent_upper.clone() },
                Formula::Imply(left, right) => Formula::Imply(Box::new(inner_rewrite(left)), Box::new(inner_rewrite(right))),
                Formula::U { interval, left, right, .. } => {
                    let new_left = inner_rewrite(left);
                    let new_right = inner_rewrite(right);
                    let first = Formula::U { 
                        interval: interval.clone(), 
                        parent_upper: None, 
                        left: Box::new(new_left.clone()), 
                        right: Box::new(new_right.clone())
                    };
                    let second = Formula::G { 
                        interval: Interval { lower: 0, upper: interval.lower }, 
                        parent_upper: None, 
                        phi: Box::new(new_left.clone()) 
                    };
                    Formula::And(vec![first, second])
                } 
                Formula::R { interval, left, right, .. } => {
                    let new_left = inner_rewrite(left);
                    let new_right = inner_rewrite(right);
                    let first = Formula::F { 
                        interval: Interval { lower: 0, upper: interval.lower }, 
                        parent_upper: None, 
                        phi: Box::new(new_left.clone())
                    };
                    let second = Formula::R { 
                        interval: interval.clone(), 
                        parent_upper: None, 
                        left: Box::new(new_left.clone()),
                        right: Box::new(new_right.clone())
                    };
                    Formula::Or(vec![first, second])
                }
                _ => formula.clone()
            }
        }
        self.operands.iter_mut().for_each(|f| {
            *f = inner_rewrite(f);
        });
    }

    pub fn push_negation(&mut self) {
        fn inner_rewrite(formula: &Formula) -> Formula {
            if let Formula::Not(inner) = formula {
                match &**inner {
                    Formula::Not(i) => inner_rewrite(&i),
                    Formula::And(ops) => Formula::Or(ops.iter().map(|f| inner_rewrite(&Formula::Not(Box::new(f.clone())))).collect()),
                    Formula::Or(ops) => Formula::And(ops.iter().map(|f| inner_rewrite(&Formula::Not(Box::new(f.clone())))).collect()),
                    Formula::Imply(left, right) => Formula::And(vec![*left.clone(), inner_rewrite(&Formula::Not(Box::new(*right.clone())))]),
                    Formula::G { phi, interval, parent_upper } => Formula::F { 
                        phi: Box::new(inner_rewrite(&Formula::Not(Box::new(*phi.clone())))), interval: interval.clone(), parent_upper: parent_upper.clone() 
                    },
                    Formula::F { phi, interval, parent_upper } => Formula::G {
                        phi: Box::new(inner_rewrite(&Formula::Not(Box::new(*phi.clone())))), interval: interval.clone(), parent_upper: parent_upper.clone() 
                    },
                    Formula::U { interval, left, right, .. } => Formula::R { 
                        interval: interval.clone(), 
                        parent_upper: None, 
                        left: Box::new(inner_rewrite(&Formula::Not(Box::new(*left.clone())))), 
                        right: Box::new(inner_rewrite(&Formula::Not(Box::new(*right.clone()))))
                    },
                    Formula::R { interval, left, right, .. } => Formula::U { 
                        interval: Interval { lower: 0, upper: interval.lower }, 
                        parent_upper: None, 
                        left: Box::new(inner_rewrite(&Formula::Not(Box::new(*left.clone())))), 
                        right: Box::new(inner_rewrite(&Formula::Not(Box::new(*right.clone()))))
                    },
                    Formula::O(i) => Formula::O(Box::new(inner_rewrite(&Formula::Not(Box::new(*i.clone()))))),
                    _ => formula.clone()
                }
            } else {
                formula.clone()
            }
        }
        self.operands.iter_mut().for_each(|f| {
            *f = inner_rewrite(f);
        });
    }

    pub fn shift_bounds(&mut self) {
        fn get_shift(formula: &Formula) -> Option<i32> {
            match formula {
                Formula::O(inner) 
                | Formula::Not(inner) => get_shift(inner),
                Formula::And(operands) 
                | Formula::Or(operands) => {
                    operands.iter().map(|op| get_shift(op)).min().unwrap()
                },
                Formula::Imply(left, right) => get_shift(left).min(get_shift(right)),
                Formula::G { interval, .. } 
                | Formula::F { interval, .. } 
                | Formula::U { interval, .. }
                | Formula::R { interval, .. } => Some(interval.lower),
                _ => None,
            }
        }
        fn shift_backward(formula: &mut Formula, shift: i32) {
            match formula {
                Formula::And(ops) => ops.iter_mut().for_each(|f| shift_backward(f, shift)),
                Formula::Or(ops) => ops.iter_mut().for_each(|f| shift_backward(f, shift)),
                Formula::Imply(left, right) => {
                    shift_backward(left, shift);
                    shift_backward(right, shift);
                },
                Formula::O(i) => shift_backward(i, shift),
                Formula::Not(i) => shift_backward(i, shift),
                Formula::G { interval, .. } | Formula::F { interval, .. } | Formula::U { interval, .. } | Formula::R { interval, .. } => {
                    interval.lower -= shift;
                    interval.upper -= shift;
                },
                _ => {}
            }
        }
        fn inner_rewrite(formula: &mut Formula) {
            match formula {
                Formula::And(ops) => ops.iter_mut().for_each(|f| inner_rewrite(f)),
                Formula::Or(ops) => ops.iter_mut().for_each(|f| inner_rewrite(f)),
                Formula::O(i) | Formula::Not(i) => inner_rewrite(i),
                Formula::Imply(left, right) => {
                    inner_rewrite(left); 
                    inner_rewrite(right);
                },
                Formula::G { phi, interval, .. } | Formula::F { phi, interval, .. } => {
                    inner_rewrite(phi);
                    if let Some(shift) = get_shift(phi) {
                        shift_backward(phi, shift);
                        interval.lower += shift;
                        interval.upper += shift;
                    }
                },
                Formula::U { interval, left, right, .. } | Formula::R { interval, left, right, .. } => {
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

    pub fn flatten(&mut self) {
        fn flatten_operand(formula: &mut Formula) {
            match formula {
                Formula::And(ops) => {
                    ops.iter_mut().for_each(flatten_operand);
                    let mut flattened: Vec<Formula> = Vec::new();
                    ops.iter_mut().for_each(|f| {
                        if let Formula::And(inner_ops) = f {
                            flattened.append(inner_ops);
                        } else {
                            flattened.push(f.clone());
                        }
                    });
                    *ops = flattened;
                },
                Formula::Or(ops) => {
                    ops.iter_mut().for_each(flatten_operand);
                    let mut flattened: Vec<Formula> = Vec::new();
                    ops.iter_mut().for_each(|f| {
                        if let Formula::Or(inner_ops) = f {
                            flattened.append(inner_ops);
                        } else {
                            flattened.push(f.clone());
                        }
                    });
                    *ops = flattened;
                },
                Formula::Not(inner)
                | Formula::O(inner) 
                | Formula::G { phi: inner, .. } 
                | Formula::F { phi: inner, .. } => flatten_operand(inner),
                Formula::U { left, right, .. } 
                | Formula::R { left, right, .. }
                | Formula::Imply(left, right) => {
                    flatten_operand(left);
                    flatten_operand(right);
                },
                _ => {}
            }
        }

        let mut flattened: Vec<Formula> = Vec::new();
        self.operands.iter_mut().for_each(|f| {
            flatten_operand(f);
            if let Formula::And(ops) = f {
                flattened.append(ops);
            } else {
                flattened.push(f.clone());
            }
        });
        self.operands = flattened;
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