use core::fmt;
use std::{collections::HashSet, fmt::Display, hash::Hash};

use crate::{formula::*, node::Node};

#[derive(Hash, PartialEq, Eq)]
pub struct RejectedNode {
    operands: Vec<Formula>,
}

impl RejectedNode {
    pub fn from_node(node: &Node) -> Self {
        RejectedNode { 
            operands: node.operands.iter().map(|f| {
                let mut new_f = f.clone();
                match &mut new_f {
                    Formula::G { interval, .. }
                    | Formula::F { interval, .. }
                    | Formula::U { interval, .. }
                    | Formula::R { interval, .. } => {
                        interval.shift(node.current_time);
                    }
                    _ => {}
                }
            new_f
            }).collect() 
        }
    }
}

impl Display for RejectedNode {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        let join_with = |v: &[Formula], sep: &str| {
            v.iter().map(|n| n.to_string()).collect::<Vec<_>>().join(sep)
        };
        write!(f, "{}", join_with(&self.operands, ", "))
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
    fn quick_implies(&self, other: &Formula) -> bool {
        match (self, other) {
            (f1, f2) if f1 == f2 => true,
            (Formula::G { interval: i1, phi: f1, .. }, 
             Formula::G { interval: i2, phi: f2, .. }) => {
                i1.contains(&i2) && f1.quick_implies(f2)
            }
            (Formula::F { interval: i1, phi: f1, .. },
             Formula::F { interval: i2, phi: f2, .. }) => {
                i2.contains(&i1) && f1.quick_implies(f2)
            },
            (Formula::Not(f1), Formula::Not(f2)) => {
                f1.quick_implies(&f2)
            },
            _ => false
        }
    }
}

impl RejectedNode {
    fn implies(&self, other: &RejectedNode) -> bool {
        other.operands.iter().all(|rf| 
            self.operands.iter().any(|lf| lf.quick_implies(rf)))
    }
}