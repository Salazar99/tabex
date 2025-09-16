// Local solver for STL consistency checking
// Simplified implementation for boolean variables only

use crate::node::Node;
use crate::formula::{Formula, Expr};
use std::collections::HashSet;

#[derive(Clone)]
struct BooleanSolver {
    pos_props: HashSet<String>,
    neg_props: HashSet<String>,
    result_cache: Option<bool>,
}

impl BooleanSolver {
    fn new() -> Self {
        BooleanSolver {
            pos_props: HashSet::new(),
            neg_props: HashSet::new(),
            result_cache: Some(true),
        }
    }

    fn add_constraint(&mut self, negated: bool, prop: String) {
        if negated {
            self.neg_props.insert(prop.clone());
            if self.pos_props.contains(&prop) {
                self.result_cache = Some(false);
            }
        } else {
            self.pos_props.insert(prop.clone());
            if self.neg_props.contains(&prop) {
                self.result_cache = Some(false);
            }
        }
    }

    fn remove_constraint(&mut self, negated: bool, prop: &str) {
        if negated {
            self.neg_props.remove(prop);
        } else {
            self.pos_props.remove(prop);
        }
        if self.result_cache == Some(false) {
            self.result_cache = None;
        }
    }

    fn check(&mut self) -> bool {
        if let Some(res) = self.result_cache {
            res
        } else {
            let res = self.pos_props.is_disjoint(&self.neg_props);
            self.result_cache = Some(res);
            res
        }
    }
}

#[derive(Clone)]
pub struct Solver {
    boolean_solver: BooleanSolver,
    current_assertions: HashSet<(bool, String)>,
    assertion_stack: Vec<Vec<(bool, String)>>,
    result_cache: Option<bool>,
}

impl Solver {
    pub fn new() -> Self {
        Solver {
            boolean_solver: BooleanSolver::new(),
            current_assertions: HashSet::new(),
            assertion_stack: Vec::new(),
            result_cache: Some(true),
        }
    }

    pub fn get_empty_solver(&self) -> Solver {
        Solver {
            boolean_solver: BooleanSolver::new(),
            current_assertions: HashSet::new(),
            assertion_stack: Vec::new(),
            result_cache: Some(true),
        }
    }

    pub fn push(&mut self) {
        self.assertion_stack.push(Vec::new());
    }

    pub fn pop(&mut self) {
        if let Some(old_assertions) = self.assertion_stack.pop() {
            let len = old_assertions.len();
            for ass in old_assertions {
                self.current_assertions.remove(&ass);
                let (negated, term) = ass;
                self.boolean_solver.remove_constraint(negated, &term);
            }
            if len > 0 {
                self.result_cache = None;
            }
        }
    }

    fn add_boolean_constraint(&mut self, negated: bool, prop: String) {
        let entry = (negated, prop.clone());
        if !self.current_assertions.contains(&entry) {
            self.current_assertions.insert(entry.clone());
            if let Some(last) = self.assertion_stack.last_mut() {
                last.push(entry);
            }
            self.boolean_solver.add_constraint(negated, prop);
            if self.result_cache == Some(true) {
                self.result_cache = Some(self.boolean_solver.check());
            }
        }
    }

    fn add_constraints(&mut self, node: &Node) {
        for operand in &node.operands {
            match operand {
                Formula::Prop(Expr::Atom(expr)) => {
                    self.add_boolean_constraint(false, expr.clone());
                }
                Formula::Not(operand) => {
                    if let Formula::Prop(Expr::Atom(expr)) = &**operand {
                        self.add_boolean_constraint(true, expr.clone());
                    }
                }
                _ => {}
            }
        }
    }

    pub fn check(&mut self, node: &Node) -> bool {
        self.add_constraints(node);
        if let Some(res) = self.result_cache {
            res
        } else {
            let res = self.boolean_solver.check();
            self.result_cache = Some(res);
            res
        }
    }
}