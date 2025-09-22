#![allow(unused)]
use std::{fmt::{self, Display}, sync::atomic::{AtomicUsize, Ordering}};
use crate::formula::*;

static NODE_ID: AtomicUsize = AtomicUsize::new(0);

#[derive(Debug, PartialEq, Eq, Hash)]
pub struct Node {
    pub operands: Vec<Formula>,

    pub current_time: i64,
    pub jump1: bool,

    pub id: usize,
}

impl Node {
    pub fn from_operands(operands: Vec<Formula>) -> Self {
        Self {
            operands,
            current_time: 0,
            jump1: false,
            id: NODE_ID.fetch_add(1, Ordering::Relaxed),
        }
    }

    pub fn sorted_time_instants(&self) -> Vec<i64> {
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

        let mut times: Vec<i64> = self.operands.iter().filter_map(top_level_interval).flat_map(|i| [i.lower, i.upper]).collect();

        times.sort_unstable();
        times.dedup();
        times
    }
}

impl Clone for Node {
    fn clone(&self) -> Self {
        Self {
            operands: self.operands.clone(),
            current_time: self.current_time,
            jump1: self.jump1,
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