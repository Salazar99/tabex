use std::{fmt::{self, Display}, sync::atomic::{AtomicUsize, Ordering}};
use crate::formula::*;

pub mod rewrite;
pub mod decompose;

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
        write!(f, "{} | {}", join_with(&self.operands, ", "), self.current_time)
    }
}