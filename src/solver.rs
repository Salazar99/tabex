use crate::node::Node;
use crate::formula::{AExpr, ArithOp, Expr, Formula, RelOp};

use std::collections::BTreeMap;
use z3::{Solver as Z3Solver, ast::{Real, Bool}};
use std::collections::HashSet;

// Use interned strings for better memory efficiency with repeated variable names
use std::sync::Arc;

type VariableName = Arc<str>;

#[derive(Clone, PartialEq, Eq, Hash, Debug)]
pub enum Assertion {
    Boolean { negated: bool, var: VariableName },
    Real { negated: bool, op: RelOp, left: AExpr, right: AExpr },
}

pub struct Solver {
    boolean_solver: BooleanSolver,
    real_solver: RealSolver,
    assertion_stack: Vec<Vec<Assertion>>,
    current_assertions: HashSet<Assertion>,
    result_cache: Option<bool>,
}

impl Solver {
    pub fn new() -> Self {
        Solver {
            boolean_solver: BooleanSolver::new(),
            real_solver: RealSolver::new(),
            result_cache: Some(true),
            assertion_stack: Vec::with_capacity(64),
            current_assertions: HashSet::with_capacity(128),
        }
    }

    pub fn push(&mut self) {
        self.assertion_stack.push(Vec::with_capacity(16));
        self.real_solver.push();
    }

    pub fn pop(&mut self) {
        if let Some(old_assertions) = self.assertion_stack.pop() {
            if !old_assertions.is_empty() {
                self.result_cache = None;
            }

            for ass in old_assertions {
                self.current_assertions.remove(&ass);
                if let Assertion::Boolean { negated, ref var } = ass {
                    self.boolean_solver.remove_constraint(negated, var);
                }
            }
        }
        self.real_solver.pop();
    }

    fn add_constraints(&mut self, node: &Node) {
        fn get_assertion(formula: &Formula) -> Option<Assertion> {
            match formula {
                Formula::Prop(Expr::Atom(expr)) => Some(Assertion::Boolean {
                    negated: false,
                    var: expr.clone(),
                }),
                Formula::Prop(Expr::Rel { left, right, op }) => Some(Assertion::Real {
                    negated: false,
                    op: op.clone(),
                    left: left.clone(),
                    right: right.clone(),
                }),
                Formula::Not(inner) => {
                    match get_assertion(&inner)? {
                        Assertion::Boolean { negated, var } => Some(Assertion::Boolean {
                            negated: !negated,
                            var,
                        }),
                        Assertion::Real { negated, op, left, right } => Some(Assertion::Real {
                            negated: !negated,
                            op,
                            left,
                            right,
                        }),
                    }
                }
                _ => None,
            }
        }
        node.operands.iter().filter_map(|f| get_assertion(f)).for_each(|ass| {
            if self.current_assertions.insert(ass.clone()) {
                match ass {
                    Assertion::Boolean { negated, ref var } => {
                        self.boolean_solver.add_constraint(negated, var);
                    }
                    Assertion::Real { negated, ref op, ref left, ref right } => {
                        self.real_solver.add_constraint(negated, op.clone(), left.clone(), right.clone());
                    }
                }
                
                if let Some(last) = self.assertion_stack.last_mut() {
                    last.push(ass);
                }
            }
        });
    }

    pub fn check(&mut self, node: &Node) -> bool {
        if node.operands.iter().any(|f| {
            match f {
                Formula::O(inner) => {
                    match &**inner {
                        Formula::F { interval, .. } | Formula::U { interval, .. } if node.current_time == interval.upper => true,
                        _ => false
                    }
                },
                Formula::False => true,
                Formula::Not(inner) if matches!(**inner, Formula::True) => true,
                _ => false
            }
        }) {
            return false;
        }
        self.add_constraints(node);
        let bool_ok = self.boolean_solver.check();
        let real_ok = self.real_solver.check();
        let res = bool_ok && real_ok;
        self.result_cache = Some(res);
        res
    }

}

struct BooleanSolver {
    pos_props: HashSet<Arc<str>>,
    neg_props: HashSet<Arc<str>>,
    result_cache: Option<bool>,
}

impl BooleanSolver {
    fn new() -> Self {
        BooleanSolver {
            pos_props: HashSet::with_capacity(64),
            neg_props: HashSet::with_capacity(64),
            result_cache: Some(true),
        }
    }

    fn add_constraint(&mut self, negated: bool, prop: &Arc<str>) {
        if negated {
            self.neg_props.insert(prop.clone());
            if self.pos_props.contains(&**prop) {
                self.result_cache = Some(false);
            }
        } else {
            self.pos_props.insert(prop.clone());
            if self.neg_props.contains(&**prop) {
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
struct RealSolver {
    z3_solver: Z3Solver,
    z3_variables: BTreeMap<String, Real>,
    result_cache: Option<bool>,
}

impl RealSolver {
    fn new() -> Self {
        RealSolver {
            z3_solver: Z3Solver::new(),
            z3_variables: BTreeMap::new(),
            result_cache: Some(true),
        }
    }

    fn push(&mut self) {
        self.z3_solver.push();
    }

    fn pop(&mut self) {
        self.z3_solver.pop(1);
    }

    fn add_constraint(&mut self, negated: bool, op: RelOp, left: AExpr, right: AExpr) {
        let ast = self.rel_to_z3(negated, op, left, right);
        self.z3_solver.assert(&ast);
        self.result_cache = None;
    }

    fn check(&mut self) -> bool {
        if let Some(res) = self.result_cache {
            res
        } else {
            let res = self.z3_solver.check();
            let sat = res == z3::SatResult::Sat;
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