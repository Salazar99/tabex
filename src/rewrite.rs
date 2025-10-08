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
        let (phi, pu) = el.0;
        let (idx, new_interval) = el.1;
        new_operands[idx] = Formula::g(new_interval, pu, phi);
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
        if let FormulaKind::G { interval: g_int, phi, .. } = &op.kind && time + 2 <= g_int.upper &&
            let FormulaKind::F { interval: f_int, .. } = &phi.kind && op.active(time) {
                let first = op.with_interval(Interval { lower: time + 2, upper: g_int.upper });

                let second = Formula::or(vec![
                    phi.with_interval(Interval { lower: time + f_int.lower + 1, upper: time + f_int.upper }),
                    Formula::and(vec![
                        phi.with_interval(Interval { lower: time + f_int.lower, upper: time + f_int.lower }),
                        phi.with_interval(Interval { lower: time + f_int.upper + 1, upper: time + f_int.upper + 1 })
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
        fn inner_rewrite(formula: &mut Formula) {
            match &mut formula.kind {
                FormulaKind::And(ops)
                | FormulaKind::Or(ops) => ops.iter_mut().for_each(|f| inner_rewrite(f)),
                FormulaKind::O(i)
                | FormulaKind::Not(i)
                | FormulaKind::G { phi: i, .. }
                | FormulaKind::F { phi: i, ..} => inner_rewrite(i),
                FormulaKind::Imply(left, right) => { inner_rewrite(left); inner_rewrite(right);},
                FormulaKind::U { interval, left, right, .. } => {
                    inner_rewrite(left);
                    inner_rewrite(right);
                    formula.kind = FormulaKind::And(vec![
                        Formula::g(Interval { lower: 0, upper: interval.lower }, None, (**left).clone()),
                        formula.clone(),
                    ]);
                } 
                FormulaKind::R { interval, left, right, .. } => {
                    inner_rewrite(left);
                    inner_rewrite(right);
                    formula.kind = FormulaKind::Or(vec![
                        Formula::f(Interval { lower: 0, upper: interval.lower }, None, (**left).clone()),
                        formula.clone(),
                    ]);
                }
                _ => {}
            }
        }
        self.operands.iter_mut().for_each(|f| {
            inner_rewrite(f);
        });
    }

    pub fn push_negation(&mut self) {
        fn inner_rewrite(formula: &Formula) -> Formula {
            if let FormulaKind::Not(inner) = &formula.kind {
                match &inner.kind {
                    FormulaKind::Not(i) => inner_rewrite(i),
                    FormulaKind::And(ops) => Formula::or(ops.iter().map(|f| inner_rewrite(&Formula::not(f.clone()))).collect()),
                    FormulaKind::Or(ops) => Formula::and(ops.iter().map(|f| inner_rewrite(&Formula::not(f.clone()))).collect()),
                    FormulaKind::Imply(left, right) => Formula::and(vec![*left.clone(), inner_rewrite(&Formula::not(*right.clone()))]),
                    FormulaKind::G { phi, interval, parent_upper } => Formula::f(interval.clone(), *parent_upper, inner_rewrite(&Formula::not(*phi.clone()))),
                    FormulaKind::F { phi, interval, parent_upper } => Formula::g(interval.clone(), *parent_upper, inner_rewrite(&Formula::not(*phi.clone()))),
                    FormulaKind::U { interval, left, right, parent_upper } => Formula::r(interval.clone(), *parent_upper, inner_rewrite(&Formula::not(*left.clone())), inner_rewrite(&Formula::not(*right.clone()))),
                    FormulaKind::R { interval, left, right, parent_upper } => Formula::u(Interval { lower: 0, upper: interval.lower }, *parent_upper, inner_rewrite(&Formula::not(*left.clone())), inner_rewrite(&Formula::not(*right.clone()))),
                    FormulaKind::O(i) => Formula::o(inner_rewrite(&Formula::not(*i.clone()))),
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
            match &formula.kind {
                FormulaKind::O(inner) 
                | FormulaKind::Not(inner) => get_shift(inner),
                FormulaKind::And(operands) 
                | FormulaKind::Or(operands) => {
                    operands.iter().map(|op| get_shift(op)).min().unwrap_or(None)
                },
                FormulaKind::Imply(left, right) => get_shift(left).min(get_shift(right)),
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
                FormulaKind::Imply(left, right) => {
                    shift_backward(left, shift);
                    shift_backward(right, shift);
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
                FormulaKind::Imply(left, right) => {
                    inner_rewrite(left); 
                    inner_rewrite(right);
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

    pub fn flatten(&mut self) {
        fn flatten_operand(formula: &mut Formula) {
            match &mut formula.kind {
                FormulaKind::And(ops) => {
                    ops.iter_mut().for_each(flatten_operand);
                    let mut flattened: Vec<Formula> = Vec::new();
                    for f in ops.iter() {
                        if let FormulaKind::And(inner_ops) = &f.kind {
                            flattened.extend(inner_ops.iter().cloned());
                        } else {
                            flattened.push(f.clone());
                        }
                    }
                    *ops = flattened;
                },
                FormulaKind::Or(ops) => {
                    ops.iter_mut().for_each(flatten_operand);
                    let mut flattened: Vec<Formula> = Vec::new();
                    for f in ops.iter() {
                        if let FormulaKind::Or(inner_ops) = &f.kind {
                            flattened.extend(inner_ops.iter().cloned());
                        } else {
                            flattened.push(f.clone());
                        }
                    }
                    *ops = flattened;
                },
                FormulaKind::Not(inner)
                | FormulaKind::O(inner) 
                | FormulaKind::G { phi: inner, .. } 
                | FormulaKind::F { phi: inner, .. } => flatten_operand(inner),
                FormulaKind::U { left, right, .. } 
                | FormulaKind::R { left, right, .. }
                | FormulaKind::Imply(left, right) => {
                    flatten_operand(left);
                    flatten_operand(right);
                },
                _ => {}
            }
        }

        let mut flattened: Vec<Formula> = Vec::new();
        for f in &mut self.operands {
            flatten_operand(f);
            if let FormulaKind::And(ops) = &f.kind {
                flattened.extend(ops.iter().cloned());
            } else {
                flattened.push(f.clone());
            }
        }
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