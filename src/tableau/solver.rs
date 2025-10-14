use crate::node::Node;
use crate::formula::{AExpr, ArithOp, Expr, Formula, RelOp};

use std::collections::{BTreeMap, HashMap};
use z3::ast::Ast;
use z3::{Solver as Z3Solver, ast::{Real, Bool}};
use std::collections::HashSet;

use std::sync::Arc;

#[cfg(test)]
mod tests;

#[derive(Clone, Debug)]
pub struct Assertion {
    pub id: usize,
    pub expr: Expr,
    pub negated: bool,
}

impl PartialEq for Assertion {
    fn eq(&self, other: &Self) -> bool {
        self.expr == other.expr && self.negated == other.negated
    }
}

impl Eq for Assertion {}

impl std::hash::Hash for Assertion {
    fn hash<H: std::hash::Hasher>(&self, state: &mut H) {
        self.expr.hash(state);
        self.negated.hash(state);
    }
}

pub struct Solver {
    unsat_core_extraction: bool,

    boolean_solver: BooleanSolver,
    real_solver: RealSolver,
}

impl Solver {
    pub fn new(unsat_core_extraction: bool) -> Self {
        Solver {
            unsat_core_extraction: unsat_core_extraction,

            boolean_solver: BooleanSolver::new(unsat_core_extraction),
            real_solver: RealSolver::new(unsat_core_extraction),
        }
    }

    pub fn empty_solver(&self) -> Self {
        let mut solver = Solver::new(self.unsat_core_extraction);
        solver.real_solver.z3_variables = self.real_solver.z3_variables.clone();
        solver.real_solver.z3_ast_cache = self.real_solver.z3_ast_cache.clone();
        solver
    }

    pub fn push(&mut self) {
        self.boolean_solver.push();
        self.real_solver.push();
    }

    pub fn pop(&mut self) {
        self.boolean_solver.pop();
        self.real_solver.pop();
    }

    fn add_constraints(&mut self, node: &Node) {
        fn get_assertion(formula: &Formula) -> Option<Assertion> {
            match &formula {
                Formula::Prop(id, expr) => Some(Assertion { id: *id, expr: expr.clone(), negated: false }),
                Formula::Not(inner) => {
                    get_assertion(inner).map(|mut ass| {
                        ass.negated = !ass.negated;
                        ass
                    })
                }
                _ => None,
            }
        }
        node.operands.iter().filter_map(|f| {
            get_assertion(f)
        }).for_each(|ass| {
            match &ass.expr {
                Expr::Atom(var) => {
                    self.boolean_solver.add_constraint(ass.negated, var, ass.id);
                }
                Expr::Rel { left, right, op } => {
                    self.real_solver.add_constraint(ass.negated, op.clone(), left.clone(), right.clone(), ass.id);
                }
            }
        });
    }

    pub fn check(&mut self, node: &Node) -> bool {
        if node.operands.iter().any(|f| {
            match &f {
                Formula::False(_) => true,
                Formula::Not(inner) if matches!(**inner, Formula::True(_)) => true,
                _ => false
            }
        }) {
            return false;
        }
        self.add_constraints(node);
        let bool_ok = self.boolean_solver.check();
        let real_ok = self.real_solver.check();
        let res = bool_ok && real_ok;
        res
    }

    pub fn extract_unsat_core(&self) -> Option<Vec<usize>> {
        if let Some(vec) = self.boolean_solver.unsat_core.clone() {
            return Some(vec);
        }
        return self.real_solver.unsat_core.clone();
    }

}
struct BooleanSolver {
    pos_props: HashMap<Arc<str>, usize>,
    neg_props: HashMap<Arc<str>, usize>,
    constraint_stack: Vec<Vec<(bool, Arc<str>)>>,

    result_cache: Option<bool>,

    unsat_core_extraction: bool,
    unsat_core: Option<Vec<usize>>,
}

impl BooleanSolver {
    fn new(unsat_core_extraction: bool) -> Self {
        BooleanSolver {
            pos_props: HashMap::with_capacity(64),
            neg_props: HashMap::with_capacity(64),
            constraint_stack: Vec::new(),
            result_cache: Some(true),
            unsat_core_extraction: unsat_core_extraction,
            unsat_core: None,
        }
    }

    fn push(&mut self) {
        self.constraint_stack.push(Vec::new());
    }

    fn pop(&mut self) {
        if let Some(last) = self.constraint_stack.pop() {
            for (negated, prop) in last {
                self.remove_constraint(negated, &prop);
            }
        }
    }

    fn add_constraint(&mut self, negated: bool, prop: &Arc<str>, id: usize) {
        if negated {
            self.neg_props.insert(prop.clone(), id);
            if let Some(id_stored) = self.pos_props.get(&**prop) {
                self.result_cache = Some(false);
                if self.unsat_core_extraction {
                    self.unsat_core = Some(vec![*id_stored, id])
                }
            }
        } else {
            self.pos_props.insert(prop.clone(), id);
            if let Some(id_stored) = self.neg_props.get(&**prop) {
                self.result_cache = Some(false);
                if self.unsat_core_extraction {
                    self.unsat_core = Some(vec![*id_stored, id])
                }
            }
        }
        if let Some(last) = self.constraint_stack.last_mut() {
            last.push((negated, prop.clone()));
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
            let res = !self.pos_props.keys().any(|pos| self.neg_props.contains_key(pos));
            self.result_cache = Some(res);
            if self.unsat_core_extraction && !res {
                for (prop, id) in self.pos_props.iter() {
                    if let Some(neg_id) = self.neg_props.get(prop) {
                        self.unsat_core = Some(vec![*id, *neg_id]);
                        break;
                    }
                }
            }
            res
        }
    }
}
struct RealSolver {    
    z3_solver: Z3Solver,
    z3_variables: BTreeMap<String, Real>,
    z3_ast_cache: HashMap<(bool, RelOp, AExpr, AExpr), Bool>,
    current_constraints: HashSet<(bool, RelOp, AExpr, AExpr)>,
    constraint_stack: Vec<Vec<(bool, RelOp, AExpr, AExpr)>>,
    result_cache: Option<bool>,
    unsat_core_extraction: bool,
    unsat_core: Option<Vec<usize>>,
}

impl RealSolver {
    fn new(unsat_core_extraction: bool) -> Self {
        RealSolver {
            z3_solver: Z3Solver::new(),
            z3_variables: BTreeMap::new(),
            z3_ast_cache: HashMap::new(),
            current_constraints: HashSet::new(),
            constraint_stack: Vec::new(),
            result_cache: Some(true),
            unsat_core_extraction: unsat_core_extraction,
            unsat_core: None,
        }
    }

    fn push(&mut self) {
        self.constraint_stack.push(Vec::new());
        self.z3_solver.push();
    }

    fn pop(&mut self) {
        if let Some(last) = self.constraint_stack.pop() {
            for key in last {
                self.current_constraints.remove(&key);
            }
        }
        self.z3_solver.pop(1);
        if self.result_cache == Some(false) {
            self.result_cache = None;
        }
    }

    fn add_constraint(&mut self, negated: bool, op: RelOp, left: AExpr, right: AExpr, id: usize) {
        let key = (negated, op.clone(), left.clone(), right.clone());
        if self.current_constraints.insert(key.clone()) {
            let ast = if let Some(b) = self.z3_ast_cache.get(&key) {
                b.clone()
            } else {
                let value = self.rel_to_z3(negated, op, left, right);
                self.z3_ast_cache.insert(key.clone(), value.clone());
                value
            };

            if !self.unsat_core_extraction {
                self.z3_solver.assert(ast);
            } else {
                let p = z3::ast::Bool::new_const(format!("p_{}", id).as_str());
                self.z3_solver.assert_and_track(ast, &p);
            }
            self.result_cache = None;
            if let Some(last) = self.constraint_stack.last_mut() {
                last.push(key);
            }
        }
    }

    fn check(&mut self) -> bool {
        if let Some(res) = self.result_cache {
            res
        } else {
            let res = self.z3_solver.check();
            let sat = res == z3::SatResult::Sat;
            if self.unsat_core_extraction && !sat {
                let unsat_core = self.z3_solver.get_unsat_core();
                let mut core_ids = Vec::new();
                for expr in unsat_core.iter() {
                    let name = expr.decl().name();
                    if name.starts_with("p_") {
                        if let Ok(id) = name[2..].parse::<usize>() {
                            core_ids.push(id);
                        }
                    }
                }
                self.unsat_core = Some(core_ids);
            }
            self.result_cache = Some(sat);
            sat
        }
    }

    fn aexpr_to_z3(&mut self, expr: &AExpr) -> Real {
        match expr {
            AExpr::Var(name) => {
                let name_str = name.to_string();
                if let Some(v) = self.z3_variables.get(&name_str) {
                    v.clone()
                } else {
                    let v = Real::new_const(name_str.as_str());
                    self.z3_variables.insert(name_str, v.clone());
                    v
                }
            }
            AExpr::Num(r) => Real::from_rational(*r.numer(), *r.denom()),
            AExpr::Abs(inner) => {
                let x = self.aexpr_to_z3(inner);
                let zero = Real::from_rational(0, 1);
                let cond = x.ge(&zero);
                let neg_x = &zero - &x;
                Bool::ite(&cond, &x, &neg_x)
            }
            AExpr::BinOp { op, left, right } => {
                let l = self.aexpr_to_z3(left);
                let r = self.aexpr_to_z3(right);
                match op {
                    ArithOp::Add => &l + &r,
                    ArithOp::Sub => &l - &r,
                }
            }
        }
    }

    fn rel_to_z3(&mut self, negated: bool, op: RelOp, left: AExpr, right: AExpr) -> Bool {
        let l = self.aexpr_to_z3(&left);
        let r = self.aexpr_to_z3(&right);
        let b = match op {
            RelOp::Lt => l.lt(&r),
            RelOp::Le => l.le(&r),
            RelOp::Gt => l.gt(&r),
            RelOp::Ge => l.ge(&r),
            RelOp::Eq => l.eq(&r),
            RelOp::Ne => l.eq(&r).not(),
        };
        if negated { b.not() } else { b }
    }
}