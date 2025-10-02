#![allow(unused)]
use std::{fmt::{self, Display}, sync::atomic::{AtomicUsize, Ordering}};
use crate::formula::*;

pub static NODE_ID: AtomicUsize = AtomicUsize::new(0);

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

    pub fn sorted_time_instants(&self, current_time: i32) -> Vec<i32> {
        fn top_level_interval(formula: &Formula, current_time: i32) -> Option<&Interval> {
            match formula {
                Formula::O(inner) => top_level_interval(inner, current_time),
                Formula::G { interval, .. } 
                | Formula::F { interval, .. } 
                | Formula::U { interval, .. }
                | Formula::R { interval, .. } if !formula.parent_active(current_time) => Some(interval),
                _ => None
            }
        }

        let mut times: Vec<i32> = self.operands.iter().filter_map(|f| top_level_interval(f, current_time)).flat_map(|i| [i.lower - 1, i.upper]).collect();

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