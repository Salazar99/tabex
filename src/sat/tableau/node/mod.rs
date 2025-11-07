use crate::formula::{
    Formula, join_with,
    transform::{
        FlatTransformer, FormulaSimplifier, MLTLTransformer, NegationNormalFormTransformer,
        RecursiveFormulaTransformer, ShiftBoundsTransformer,
    },
};
use std::{
    fmt::{self, Display},
    sync::atomic::{AtomicUsize, Ordering},
};

pub mod decompose;
pub mod rewrite;

pub static NODE_ID: AtomicUsize = AtomicUsize::new(0);

#[derive(Debug, PartialEq, Eq, Hash)]
pub struct Node {
    pub operands: Vec<Formula>,
    pub current_time: i32,
    pub implies: Option<Vec<usize>>,
    pub id: usize,
}

impl Node {
    pub fn from_operands(operands: Vec<Formula>) -> Self {
        Self {
            operands,
            current_time: 0,
            implies: None,
            id: NODE_ID.fetch_add(1, Ordering::Relaxed),
        }
    }

    #[must_use]
    pub fn is_poised(&self) -> bool {
        for formula in &self.operands {
            match formula {
                Formula::Prop(_) | Formula::Not(_) | Formula::O(_) => continue,
                f if !f.is_active_at(self.current_time) => continue,
                _ => return false,
            }
        }
        true
    }

    #[must_use]
    pub fn to_formula(&self) -> Formula {
        if self.operands.len() == 1 {
            self.operands[0].clone()
        } else {
            Formula::And(self.operands.clone())
        }
    }

    pub fn mltl_rewrite(&mut self) {
        self.operands.iter_mut().for_each(|f| {
            *f = MLTLTransformer.visit(f);
        });
    }

    pub fn negative_normal_form_rewrite(&mut self) {
        self.operands.iter_mut().for_each(|f| {
            *f = NegationNormalFormTransformer.visit(f);
        });
    }

    pub fn flatten(&mut self) {
        let mut flattened: Vec<Formula> = Vec::new();
        for f in &self.operands {
            let flat = FlatTransformer.visit(f);
            if let Formula::And(ops) = &flat {
                flattened.extend(ops.iter().cloned());
            } else {
                flattened.push(flat);
            }
        }
        self.operands = flattened;
    }

    pub fn shift_bounds(&mut self) {
        self.operands.iter_mut().for_each(|f| {
            *f = ShiftBoundsTransformer.visit(f);
        });
    }

    pub fn simplify(&mut self) {
        self.operands.iter_mut().for_each(|f| {
            *f = FormulaSimplifier.visit(f);
        });
    }
}

impl Clone for Node {
    fn clone(&self) -> Self {
        Self {
            operands: self.operands.clone(),
            current_time: self.current_time,
            implies: None,
            id: NODE_ID.fetch_add(1, Ordering::Relaxed),
        }
    }
}

impl Display for Node {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        write!(
            f,
            "{} | {}",
            join_with(&self.operands, ", "),
            self.current_time
        )
    }
}
