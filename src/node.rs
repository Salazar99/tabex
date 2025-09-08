#![allow(unused)]
use std::fmt::{self, Display};
use crate::formula::*;

#[derive(Clone, Debug, PartialEq, Eq, Hash)]
pub struct Node {
    pub operands: Vec<Formula>,

    pub current_time: i64,
    pub identifier: Option<u64>,
    pub jump1: bool,
}

impl Node {
    pub fn from_operands(operands: Vec<Formula>) -> Self {
        Self {
            operands,
            current_time: 0,
            identifier: None,
            jump1: false,
        }
    }

    pub fn sorted_time_instants(&self) -> Vec<i64> {
        let mut times: Vec<i64> = Vec::new();
        for operand in &self.operands {
            match operand {
                Formula::G { lower, upper, .. } | Formula::F { lower, upper, .. } | Formula::U { lower, upper, .. } => {
                    times.push(*lower);
                    times.push(*upper);
                }
                Formula::O(inner) => {
                    if let Formula::G { lower, upper, .. } | Formula::F { lower, upper, .. } | Formula::U { lower, upper, .. } = **inner {
                        times.push(lower);
                        times.push(upper);
                    }
                }
                _ => {}
                
            }
        }
        times.sort_unstable();
        times.dedup();
        times
    }
}

impl Display for Node {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        let join_with = |v: &[Formula], sep: &str| {
            v.iter().map(|n| n.to_string()).collect::<Vec<_>>().join(sep)
        };
        write!(f, "{}", join_with(&self.operands, ", "))
    }
}