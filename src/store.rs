use std::{collections::HashSet, hash::Hash};

use crate::{formula::*, node::Node};

pub struct Store {
    store: HashSet<Node>
}

impl Store {
    pub fn new() -> Self {
        let store = HashSet::new();
        Store {
            store
        }
    }

    pub fn add_rejected(&mut self, node: &Node) {
        if !self.check_rejected(node) {
            self.store.insert(node.clone());
        }
    }

    pub fn check_rejected(&self, node: &Node) -> bool {
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

impl Node {
    fn implies(&self, other: &Node) -> bool {
        other.operands.iter().all(|rf| 
            self.operands.iter().any(|lf| lf.quick_implies(rf, self.current_time, other.current_time)))
    }
}