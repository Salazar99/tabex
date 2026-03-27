use std::{
    collections::{BTreeMap, BTreeSet, btree_map::Entry},
    vec,
};

use crate::{
    formula::{Formula, Interval},
    sat::tableau::node::{Node, NodeFormula},
};

#[cfg(test)]
mod tests;

#[must_use]
pub fn merge_globally(input: &[NodeFormula], time: i32) -> Option<Vec<NodeFormula>> {
    let mut map: BTreeMap<(Formula, Option<usize>), (usize, Interval)> = BTreeMap::new();
    let mut to_remove = BTreeSet::new();

    for (idx, op) in input.iter().enumerate() {
        if let Formula::G { interval, phi } = &op.kind {
            let key = (*phi.clone(), op.parent_id);
            match map.entry(key) {
                Entry::Occupied(mut occ) => {
                    let (_, int) = occ.get_mut();
                    if let (Some(interval_u), Some(int_u)) =
                        (interval.shift_left(time), int.shift_left(time))
                        && (int_u.intersects(&interval_u) || int_u.contiguous(&interval_u))
                    {
                        to_remove.insert(idx);
                        *int = int.union(interval);
                    }
                }
                Entry::Vacant(v) => {
                    v.insert((idx, interval.clone()));
                }
            }
        }
    }

    if to_remove.is_empty() {
        return None;
    }
    let mut new_operands = input.to_owned();
    for el in map {
        let (idx, new_interval) = el.1;
        new_operands[idx] = new_operands[idx]
            .clone()
            .with_kind(new_operands[idx].kind.clone().with_interval(new_interval));
    }

    new_operands = new_operands
        .iter()
        .enumerate()
        .filter(|(i, _)| !to_remove.contains(i))
        .map(|(_, f)| f.clone())
        .collect();

    Some(new_operands)
}

#[must_use]
pub fn merge_finally(input: &[NodeFormula], time: i32) -> Option<Vec<NodeFormula>> {
    let mut map: BTreeMap<(Formula, Option<usize>), (usize, Interval)> = BTreeMap::new();
    let mut to_remove = BTreeSet::new();

    for (idx, op) in input.iter().enumerate() {
        if let Formula::F { phi, interval } = &op.kind {
            let key = (*phi.clone(), op.parent_id);
            match map.entry(key) {
                Entry::Occupied(mut occ) => {
                    let (i, int) = occ.get_mut();
                    if let (Some(interval_u), Some(int_u)) =
                        (interval.shift_left(time), int.shift_left(time))
                    {
                        if interval_u.contains(&int_u) {
                            to_remove.insert(idx);
                        } else if int_u.contains(&interval_u) {
                            to_remove.insert(*i);
                            *i = idx;
                            *int = interval.clone();
                        }
                    }
                }
                Entry::Vacant(v) => {
                    v.insert((idx, interval.clone()));
                }
            }
        }
    }

    if to_remove.is_empty() {
        return None;
    }
    Some(
        input
            .iter()
            .enumerate()
            .filter(|(i, _)| !to_remove.contains(i))
            .map(|(_, f)| f.clone())
            .collect(),
    )
}

#[must_use]
pub fn rewrite_globally_finally(input: &Vec<NodeFormula>, time: i32) -> Option<Vec<NodeFormula>> {
    let mut new_operands = Vec::new();
    let mut new_nodes = Vec::new();

    for op in input {
        if let Formula::G {
            interval: g_int,
            phi,
        } = &op.kind
            && time + 2 <= g_int.upper
            && let Formula::F {
                interval: f_int, ..
            } = &**phi
            && f_int.lower < f_int.upper
            && op.is_active_at(time)
        {
            let first = op.kind.clone().with_interval(Interval {
                lower: time + 2,
                upper: g_int.upper,
            });

            let second = Formula::or(vec![
                phi.clone().with_interval(Interval {
                    lower: time + f_int.lower + 1,
                    upper: time + f_int.upper,
                }),
                Formula::and(vec![
                    phi.clone().with_interval(Interval {
                        lower: time + f_int.lower,
                        upper: time + f_int.lower,
                    }),
                    phi.clone().with_interval(Interval {
                        lower: time + f_int.upper + 1,
                        upper: time + f_int.upper + 1,
                    }),
                ]),
            ]);
            new_operands.push(first.into());
            new_nodes.push(second);
        } else {
            new_operands.push(op.clone());
        }
    }

    if new_nodes.is_empty() {
        return None;
    }

    for node in new_nodes {
        new_operands.push(node.into());
    }

    Some(new_operands)
}

impl Node {
    #[must_use]
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

        changed.then(|| {
            vec![Node {
                operands: current,
                ..self.clone()
            }]
        })
    }
}
