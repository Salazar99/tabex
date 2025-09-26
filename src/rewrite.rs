use core::time;
use std::{collections::HashMap, f32::INFINITY, hash::Hash, i32::MAX, result, vec};

use z3::ast::Int;

use crate::{formula::{Formula, Interval}, node::Node};

#[cfg(test)]
mod tests;

pub fn merge_globally(input: &Vec<Formula>) -> Option<Vec<Formula>> {
    let mut map: HashMap<(Formula, Option<i32>), (i32, Interval)> = HashMap::new();
    for op in input.iter() {
        if let Formula::G { interval, parent_upper, phi } = op {
            let mut entry = map.entry((*phi.clone(), *parent_upper)).or_insert((0, interval.clone()));
            if interval.intersects(&entry.1) {
                entry.0 += 1;
                entry.1.lower = entry.1.lower.min(interval.lower);
                entry.1.upper = entry.1.upper.max(interval.upper);
            }
        }
    }

    if map.values().all(|(c, _)| *c <= 1) {
        return None
    }

    let mut new_operands = Vec::new();
    for op in input.iter() {
        if let Formula::G { interval, parent_upper, phi } = op {
            let entry = map.get_mut(&(*phi.clone(), *parent_upper));
            if let Some(v) = entry {
                if v.0 <= 1 && v.0 >= 0 {
                    new_operands.push(op.clone());
                } else if v.0 > 1 {
                    let new_formula = Formula::G { interval: v.1.clone(), parent_upper: *parent_upper, phi: phi.clone() };
                    new_operands.push(new_formula);
                    v.0 = -1; // Mark as added
                }
            }
        } else {
            new_operands.push(op.clone());
        }
    }

    return Some(new_operands);
}

pub fn merge_finally(input: &Vec<Formula>) -> Option<Vec<Formula>> {
    let mut map: HashMap<(Formula, Option<i32>), (i32, Interval)> = HashMap::new();
    for op in input.iter() {
        if let Formula::F { interval, parent_upper, phi } = op {
            let mut entry = map.entry((*phi.clone(), *parent_upper)).or_insert((0, interval.clone()));
            if interval.intersects(&entry.1) {
                entry.0 += 1;
                entry.1.lower = entry.1.lower.max(interval.lower);
                entry.1.upper = entry.1.upper.min(interval.upper);
            }
        }
    }

    if map.values().all(|(c, _)| *c <= 1) {
        return None
    }

    let mut new_operands = Vec::new();
    for op in input.iter() {
        if let Formula::F { interval, parent_upper, phi } = op {
            let entry = map.get_mut(&(*phi.clone(), *parent_upper));
            if let Some(v) = entry {
                if v.0 <= 1 && v.0 >= 0 {
                    new_operands.push(op.clone());
                } else if v.0 > 1 {
                    let new_formula = Formula::F { interval: v.1.clone(), parent_upper: *parent_upper, phi: phi.clone() };
                    new_operands.push(new_formula);
                    v.0 = -1; // Mark as added
                }
            }
        } else {
            new_operands.push(op.clone());
        }
    }

    return Some(new_operands);
}

pub fn rewrite_globally_finally(input: &Vec<Formula>, time: i32) -> Option<Vec<Formula>> {
    let mut changed = false;
    let mut new_operands = Vec::new();

    for op in input {
        if let Formula::G { interval: g_int, phi, .. } = op && g_int.lower + 2 <= g_int.upper && op.active(time) &&
            let Formula::F { interval: f_int, phi: psi, .. } = &**phi {
            let first = Formula::G { 
                interval: Interval { lower: g_int.lower + 2, upper: g_int.upper }, 
                parent_upper: None, phi: phi.clone() 
            };
            let second = Formula::Or(vec![
                Formula::F { 
                    interval: Interval { lower: g_int.lower + f_int.lower + 1, upper: g_int.lower + f_int.upper }, 
                    parent_upper: None, phi: psi.clone() 
                },
                Formula::And(vec![
                    Formula::G { 
                        interval: Interval { lower: g_int.lower + f_int.lower, upper: g_int.lower + f_int.lower }, 
                        parent_upper: None, phi: psi.clone()
                    },
                    Formula::G { 
                        interval: Interval { lower: g_int.lower + f_int.upper + 1, upper: g_int.lower + f_int.upper + 1 }, 
                        parent_upper: None, phi: psi.clone()
                    },
                ])
            ]);
            new_operands.push(first);
            new_operands.push(second);
            changed = true;
        } else {
            new_operands.push(op.clone());
        }
    }

    if !changed {
        None
    } else {
        Some(new_operands)
    }
}

pub fn rewrite_chain(input: &Vec<Formula>, time: i32) -> Option<Vec<Formula>> {
    let mut current = input.clone();
    let mut changed_once = false;

    loop {
        let mut local_change = false;
        if let Some(res) = merge_globally(&current) {
            current = res;
            local_change = true;
        }
        if let Some(res) = merge_finally(&current) {
            current = res;
            local_change = true;
        }
        if let Some(res) = rewrite_globally_finally(&current, time) {
            current = res;
            local_change = true;
        }

        if local_change {
            changed_once = true;
        } else {
            break;
        }
    }

    if changed_once {
        return Some(current)
    } else {
        None
    }
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
}