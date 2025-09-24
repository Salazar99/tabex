use std::{collections::HashSet, hash::Hash};

use crate::{formula::*, node::Node};

#[derive(Hash, PartialEq, Eq)]
pub struct RejectedNode {
    operands: Vec<Formula>,
    time: i64
}

impl RejectedNode {
    pub fn from_node(node: &Node) -> Self {
        RejectedNode { operands: node.operands.clone(), time: node.current_time }
    }
}

pub struct Store {
    store: HashSet<RejectedNode>
}

impl Store {
    pub fn new() -> Self {
        let store = HashSet::new();
        Store {
            store
        }
    }

    pub fn add_rejected(&mut self, node: RejectedNode) {
        if !self.check_rejected(&node) {
            self.store.insert(node);
        }
    }

    pub fn check_rejected(&self, node: &RejectedNode) -> bool {
        self.store.iter().any(|n| n.implies(node))
    }
}

impl Formula {
    fn quick_implies(&self, other: &Formula, self_time: i64, other_time: i64) -> bool {
        match (self, other) {
            (f1, f2) if f1 == f2 => true,
            (Formula::G { interval: i1, phi: f1, .. }, 
             Formula::G { interval: i2, phi: f2, .. }) => {
                f1.quick_implies(f2, self_time, other_time) && i1.shift(self_time).contains(&i2.shift(other_time))
            }
            (Formula::F { interval: i1, phi: f1, .. },
             Formula::F { interval: i2, phi: f2, .. }) => {
                f1.quick_implies(f2, self_time, other_time) && i2.shift(other_time).contains(&i1.shift(self_time))
            },
            (Formula::Not(f1), Formula::Not(f2)) => {
                f1.quick_implies(&f2, self_time, other_time)
            }
            _ => false
        }
    }
}

impl RejectedNode {
    fn implies(&self, other: &RejectedNode) -> bool {
        other.operands.iter().all(|rf| 
            self.operands.iter().any(|lf| lf.quick_implies(rf, self.time, other.time)))
    }
}