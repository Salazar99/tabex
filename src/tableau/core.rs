use crate::{formula::{Formula, FormulaKind}, node::Node};
use std::collections::{HashMap, HashSet};

pub struct UnsatCore {
    map: HashMap<usize, usize>,
    node: Option<Node>,
    pub unsat_core: HashSet<usize>,
}

impl UnsatCore {
    pub fn new() -> Self {
        UnsatCore {
            map: HashMap::new(),
            node: None,
            unsat_core: HashSet::new(),
        }
    }

    fn add_formula_rec(&mut self, formula: &Formula) {
        fn add_formula_inner(core: &mut UnsatCore, formula: &Formula, id: usize) {
            match &formula.kind {
                FormulaKind::And(children) | FormulaKind::Or(children) => {
                    for child in children {
                        add_formula_inner(core, child, id);
                    }
                }
                FormulaKind::O(child)  => {
                    add_formula_inner(core, child, id);
                }
                FormulaKind::G {phi, ..} | FormulaKind::F {phi, ..} => {
                    add_formula_inner(core, phi, id);
                }
                FormulaKind::U { left, right, .. } | FormulaKind::R { left, right, .. } => {
                    add_formula_inner(core, left, id);
                    add_formula_inner(core, right, id);
                }
                FormulaKind::Imply { left, right, not_left } => {
                    add_formula_inner(core, left, id);
                    add_formula_inner(core, right, id);
                    add_formula_inner(core, not_left, id);
                }
                _ => {
                    core.map.insert(formula.id.unwrap(), id);
                }
            }
        }
        add_formula_inner(self, formula, formula.id.unwrap());
    }
    
    fn add_formula(&mut self, formula: &Formula) {
        self.add_formula_rec(formula);
    }

    fn get_tree_ends(&self) -> HashSet<usize> {
        self.unsat_core.iter().filter_map(|id| self.map.get(id)).cloned().collect::<HashSet<usize>>()
    }

    pub fn initialize_root_node(&mut self, node: &Node) {
        for formula in &node.operands {
            self.add_formula(formula);
        }
        self.node = Some(node.clone());
    }

    pub fn add_to_unsat_core(&mut self, core: Vec<usize>) {
        for id in core {
            self.unsat_core.insert(id);
        }
    }

    pub fn get_unsat_core(&self) -> Vec<Formula> {
        let mut result = Vec::new();
        let high_level_unsat_core = self.get_tree_ends();
        if let Some(node) = &self.node {
            for formula in &node.operands {
                if high_level_unsat_core.contains(&formula.id.unwrap()) {
                    result.push(formula.clone());
                }
            }
        }
        result
    }
}