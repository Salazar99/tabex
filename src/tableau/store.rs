use core::fmt;
use std::{collections::HashSet, fmt::Display, hash::Hash};

use crate::{
    formula::{Formula, join_with},
    node::Node,
};

#[cfg(test)]
mod tests;

#[derive(Clone, Hash, PartialEq, Eq)]
pub struct RejectedNode {
    operands: Vec<Formula>,
    time: i32,
}

impl RejectedNode {
    #[must_use]
    pub fn from_node(node: &Node) -> Self {
        RejectedNode {
            operands: node.operands.clone(),
            time: node.current_time,
        }
    }

    fn implies(&self, other: &RejectedNode) -> bool {
        if other.operands.iter().all(|rf| {
            self.operands
                .iter()
                .any(|lf| lf.quick_implies(rf, self.time, other.time))
        }) {
            return true;
        } else {
            let mut times: Vec<i32> = self
                .operands
                .iter()
                .filter_map(super::super::formula::Formula::lower_bound)
                .filter(|t| *t > self.time)
                .collect();
            times.sort_unstable();
            times.dedup();
            for time in times {
                if other.operands.iter().all(|rf| {
                    self.operands
                        .iter()
                        .any(|lf| lf.quick_implies(rf, time, other.time))
                }) {
                    return true;
                }
            }
        }
        false
    }
}

impl Display for RejectedNode {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        write!(f, "{} | {}", join_with(&self.operands, ", "), self.time)
    }
}

pub struct Store {
    pub store: HashSet<RejectedNode>,
}

impl Default for Store {
    fn default() -> Self {
        Self::new()
    }
}

impl Store {
    #[must_use]
    pub fn new() -> Self {
        let store = HashSet::new();
        Store { store }
    }

    pub fn add_rejected(&mut self, node: RejectedNode) {
        if !self.check_rejected(&node) {
            self.store.insert(node);
        }
    }

    #[must_use]
    pub fn check_rejected(&self, node: &RejectedNode) -> bool {
        self.store
            .iter()
            .any(|rejected: &RejectedNode| node.implies(rejected))
    }
}

impl Formula {
    fn quick_implies(&self, other: &Formula, self_time: i32, other_time: i32) -> bool {
        match (&self, &other) {
            (f1, f2) if f1.get_interval().is_none() && f2.get_interval().is_none() => f1 == f2,
            (
                Formula::G {
                    interval: i1,
                    phi: f1,
                    ..
                },
                Formula::G {
                    interval: i2,
                    phi: f2,
                    ..
                },
            ) => {
                if let (Some(i1), Some(i2)) = (i1.shift_left(self_time), i2.shift_left(other_time))
                {
                    i1.contains(&i2) && f1 == f2
                } else {
                    false
                }
            }
            (
                Formula::F {
                    interval: i1,
                    phi: f1,
                    ..
                },
                Formula::F {
                    interval: i2,
                    phi: f2,
                    ..
                },
            ) => {
                if let (Some(i1), Some(i2)) = (i1.shift_left(self_time), i2.shift_left(other_time))
                {
                    i2.contains(&i1) && f1 == f2
                } else {
                    false
                }
            }
            _ => false,
        }
    }
}
