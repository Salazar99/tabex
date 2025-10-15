use crate::{formula::Formula, node::Node, tableau::{config::TableauOptions, Tableau}};

impl Tableau {    
    pub fn check_subformulas_recursively(&mut self, formula: &Formula) -> Option<bool> {
        match formula {
            Formula::And(children) => {
                for c in children {
                    if let Some(false) = self.check_subformulas_recursively(c) {
                        return Some(false);
                    }
                }
            }
            Formula::Or(children) => {
                let all_unsat = children
                    .iter()
                    .map(|c| self.check_subformulas_recursively(c))
                    .all(|res| matches!(res, Some(false)));
                if all_unsat {
                    return Some(false);
                }
            }
            Formula::Imply { left, right, .. } => {
                let left_unsat  = self.check_subformulas_recursively(left)  == Some(false);
                let right_unsat = self.check_subformulas_recursively(right) == Some(false);
                if !left_unsat && right_unsat {
                    return Some(false);
                }
            }
            Formula::G { phi, .. } | Formula::F { phi, .. } => {
                let r = self.check_subformulas_recursively(phi);
                if r == Some(false) {
                    return r;
                }
            }
            Formula::U { right, .. } => {
                let r = self.check_subformulas_recursively(right);
                if r == Some(false) {
                    return Some(false);
                }
            }
            Formula::R { right, .. } => {
                let r = self.check_subformulas_recursively(right);
                if r == Some(false) {
                    return Some(false);
                }
            }
            _ => {},
        }
        self.try_tableau(formula)
    }

    fn try_tableau(&mut self, formula: &Formula) -> Option<bool> {
        let mut options: TableauOptions = self.options.clone();
        options.max_depth = 5;
        options.subformula_check = false;

        let mut local = Tableau::new(options);
        let node = Node::from_operands(vec![formula.clone()]);
        if let (Some(global_store), Some(local_store)) = (&self.store, &mut local.store) {
            for r in &global_store.store {
                local_store.add_rejected(r.clone());
            }
        }
        let result = local.make_tableau_from_root(node);

        if let (Some(global_store), Some(local_store)) = (&mut self.store, &local.store) {
            for r in &local_store.store {
                global_store.add_rejected(r.clone());
            }
        }

        result
    }
}