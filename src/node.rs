#![allow(unused)]
use std::{fmt::{self, Display}, sync::atomic::{AtomicUsize, Ordering}};
use crate::formula::*;

static NODE_ID: AtomicUsize = AtomicUsize::new(0);

#[derive(Debug, PartialEq, Eq, Hash)]
pub struct Node {
    pub operands: Vec<Formula>,
    pub current_time: i32,
    pub implies_siblings: bool,
    pub id: usize,
}

impl Node {
    pub fn from_operands(operands: Vec<Formula>) -> Self {
        Self {
            operands,
            current_time: 0,
            implies_siblings: false,
            id: NODE_ID.fetch_add(1, Ordering::Relaxed),
        }
    }

    pub fn sorted_time_instants(&self) -> Vec<i32> {
        fn top_level_interval(formula: &Formula) -> Option<&Interval> {
            match formula {
                Formula::O(inner) => top_level_interval(inner),
                Formula::G { parent_upper: None, interval, .. } 
                | Formula::F { parent_upper: None, interval, .. } 
                | Formula::U { parent_upper: None, interval, .. }
                | Formula::R { parent_upper: None, interval, .. } => Some(interval),
                _ => None
            }
        }

        let mut times: Vec<i32> = self.operands.iter().filter_map(top_level_interval).flat_map(|i| [i.lower - 1, i.upper]).collect();

        times.sort_unstable();
        times.dedup();
        times
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
                | Formula::R { left, right, .. }=> {
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
}

impl Clone for Node {
    fn clone(&self) -> Self {
        Self {
            operands: self.operands.clone(),
            current_time: self.current_time,
            implies_siblings: false,
            id: NODE_ID.fetch_add(1, Ordering::Relaxed),
        }
    }
}

impl Display for Node {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        let join_with = |v: &[Formula], sep: &str| {
            v.iter().map(|n| n.to_string()).collect::<Vec<_>>().join(sep)
        };
        write!(f, "{} | {}", join_with(&self.operands, ", "), self.current_time)
    }
}