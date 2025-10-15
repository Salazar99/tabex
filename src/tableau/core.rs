use crate::{formula::{Formula}, node::Node};
use std::collections::{HashMap, HashSet};

#[cfg(test)]
mod tests;

pub struct UnsatCore {
    map: HashMap<usize, usize>,
    node: Option<Node>,
    pub unsat_core: HashSet<usize>,
    single_id: Option<usize>
}

impl UnsatCore {
    pub fn new() -> Self {
        UnsatCore {
            map: HashMap::new(),
            node: None,
            unsat_core: HashSet::new(),
            single_id: None
        }
    }

    fn add_formula_rec(&mut self, formula: &Formula, index: usize) {
        fn add_formula_inner(core: &mut UnsatCore, formula: &Formula, parent_id: usize) {
            match &formula {
                Formula::And(children) | Formula::Or(children) => {
                    for child in children {
                        add_formula_inner(core, child, parent_id);
                    }
                }
                Formula::O(child) | Formula::Not(child) => {
                    add_formula_inner(core, child, parent_id);
                }
                Formula::G {phi, ..} | Formula::F {phi, ..} => {
                    add_formula_inner(core, phi, parent_id);
                }
                Formula::U { left, right, .. } | Formula::R { left, right, .. } => {
                    add_formula_inner(core, left, parent_id);
                    add_formula_inner(core, right, parent_id);
                }
                Formula::Imply { left, right, not_left } => {
                    add_formula_inner(core, left, parent_id);
                    add_formula_inner(core, right, parent_id);
                    add_formula_inner(core, not_left, parent_id);
                }
                Formula::Prop(expr) => {
                    core.map.insert(expr.id, parent_id);
                }
            }
        }
        add_formula_inner(self, formula, index);
    }
    
    fn add_formula(&mut self, formula: &Formula, index: usize) {
        self.add_formula_rec(formula, index);
    }

    fn get_tree_ends(&self) -> HashSet<usize> {
        self.unsat_core.iter().filter_map(|id| self.map.get(id)).cloned().collect::<HashSet<usize>>()
    }

    pub fn initialize_root_node(&mut self, node: &Node) {
        for (idx, formula) in node.operands.iter().enumerate() {
            self.add_formula(formula, idx);
        }
        self.node = Some(node.clone());
    }

    pub fn add_to_unsat_core(&mut self, core: Vec<usize>) {
        for id in core {
            self.unsat_core.insert(id);
        }
    }

    pub fn set_single_unsat_core(&mut self, id: usize) {
        self.single_id = Some(id);
    }

    pub fn get_unsat_core(&self) -> Vec<Formula> {
        if let Some(id) = self.single_id {
            return vec![self.node.as_ref().unwrap().operands[id].clone()];
        } 
        let mut result = Vec::new();
        let high_level_unsat_core = self.get_tree_ends();
        if let Some(node) = &self.node {
            for (idx, formula) in node.operands.iter().enumerate() {
                if high_level_unsat_core.contains(&idx) {
                    result.push(formula.clone());
                }
            }
        } else {
            panic!("UnsatCore not initialized with root node");
        }
        result
    }
}