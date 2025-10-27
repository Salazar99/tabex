use std::collections::{BTreeMap, BTreeSet};

use crate::{
    formula::{Expr, ExprKind, Formula, Interval},
    node::Node,
};

#[cfg(test)]
mod tests;

pub trait RecursiveFormulaTransformer {
    fn visit(&self, formula: &Formula) -> Formula {
        match &formula {
            Formula::And(ops) => self.visit_and(formula, ops),
            Formula::Or(ops) => self.visit_or(formula, ops),
            Formula::Not(inner) => self.visit_not(formula, inner),
            Formula::O(inner) => self.visit_next(formula, inner),
            Formula::G {
                interval,
                phi,
                parent_upper,
            } => self.visit_globally(formula, interval, phi, parent_upper),
            Formula::F {
                interval,
                phi,
                parent_upper,
            } => self.visit_finally(formula, interval, phi, parent_upper),
            Formula::U {
                interval,
                left,
                right,
                parent_upper,
            } => self.visit_until(formula, interval, left, right, parent_upper),
            Formula::R {
                interval,
                left,
                right,
                parent_upper,
            } => self.visit_release(formula, interval, left, right, parent_upper),
            Formula::Imply {
                left,
                right,
                not_left,
            } => self.visit_imply(formula, left, right, not_left),
            Formula::Prop(expr) => self.visit_leaf(formula, expr),
        }
    }

    fn visit_and(&self, formula: &Formula, ops: &[Formula]) -> Formula {
        formula.with_operands(ops.iter().map(|op| self.visit(op)).collect())
    }

    fn visit_or(&self, formula: &Formula, ops: &[Formula]) -> Formula {
        formula.with_operands(ops.iter().map(|op| self.visit(op)).collect())
    }

    fn visit_not(&self, formula: &Formula, inner: &Formula) -> Formula {
        formula.with_operand(self.visit(inner))
    }

    fn visit_next(&self, formula: &Formula, inner: &Formula) -> Formula {
        formula.with_operand(self.visit(inner))
    }

    fn visit_globally(
        &self,
        formula: &Formula,
        interval: &Interval,
        phi: &Formula,
        parent_upper: &Option<i32>,
    ) -> Formula {
        formula
            .with_interval(interval.clone())
            .with_parent_upper(*parent_upper)
            .with_operand(self.visit(phi))
    }

    fn visit_finally(
        &self,
        formula: &Formula,
        interval: &Interval,
        phi: &Formula,
        parent_upper: &Option<i32>,
    ) -> Formula {
        formula
            .with_interval(interval.clone())
            .with_parent_upper(*parent_upper)
            .with_operand(self.visit(phi))
    }

    fn visit_until(
        &self,
        formula: &Formula,
        interval: &Interval,
        left: &Formula,
        right: &Formula,
        parent_upper: &Option<i32>,
    ) -> Formula {
        formula
            .with_interval(interval.clone())
            .with_parent_upper(*parent_upper)
            .with_operand_couple(self.visit(left), self.visit(right))
    }

    fn visit_release(
        &self,
        formula: &Formula,
        interval: &Interval,
        left: &Formula,
        right: &Formula,
        parent_upper: &Option<i32>,
    ) -> Formula {
        formula
            .with_interval(interval.clone())
            .with_parent_upper(*parent_upper)
            .with_operand_couple(self.visit(left), self.visit(right))
    }

    fn visit_imply(
        &self,
        formula: &Formula,
        left: &Formula,
        right: &Formula,
        not_left: &Formula,
    ) -> Formula {
        formula.with_implication(self.visit(left), self.visit(right), self.visit(not_left))
    }

    fn visit_leaf(&self, formula: &Formula, _expr: &Expr) -> Formula {
        formula.clone()
    }
}

pub struct NegationNormalFormTransformer;
impl RecursiveFormulaTransformer for NegationNormalFormTransformer {
    fn visit_not(&self, formula: &Formula, inner: &Formula) -> Formula {
        match &inner {
            Formula::Not(i) => self.visit(i),
            Formula::And(ops) => Formula::or(
                ops.iter()
                    .map(|f| self.visit(&Formula::not(f.clone())))
                    .collect(),
            ),
            Formula::Or(ops) => Formula::and(
                ops.iter()
                    .map(|f| self.visit(&Formula::not(f.clone())))
                    .collect(),
            ),
            Formula::Imply { left, right, .. } => Formula::and(vec![
                *left.clone(),
                self.visit(&Formula::not(*right.clone())),
            ]),
            Formula::G {
                phi,
                interval,
                parent_upper,
            } => Formula::f(
                interval.clone(),
                *parent_upper,
                self.visit(&Formula::not(*phi.clone())),
            ),
            Formula::F {
                phi,
                interval,
                parent_upper,
            } => Formula::g(
                interval.clone(),
                *parent_upper,
                self.visit(&Formula::not(*phi.clone())),
            ),
            Formula::U {
                interval,
                left,
                right,
                parent_upper,
            } => Formula::r(
                interval.clone(),
                *parent_upper,
                self.visit(&Formula::not(*left.clone())),
                self.visit(&Formula::not(*right.clone())),
            ),
            Formula::R {
                interval,
                left,
                right,
                parent_upper,
            } => Formula::u(
                Interval {
                    lower: 0,
                    upper: interval.lower,
                },
                *parent_upper,
                self.visit(&Formula::not(*left.clone())),
                self.visit(&Formula::not(*right.clone())),
            ),
            Formula::O(i) => Formula::o(self.visit(&Formula::not(*i.clone()))),
            Formula::Prop(_) => formula.clone(),
        }
    }
}

struct MLTLTransformer;
impl RecursiveFormulaTransformer for MLTLTransformer {
    fn visit_until(
        &self,
        formula: &Formula,
        interval: &Interval,
        left: &Formula,
        right: &Formula,
        parent_upper: &Option<i32>,
    ) -> Formula {
        let g_part = Formula::g(
            Interval {
                lower: 0,
                upper: interval.lower,
            },
            None,
            self.visit(left),
        );
        Formula::and(vec![
            g_part,
            formula
                .with_interval(interval.clone())
                .with_parent_upper(*parent_upper)
                .with_operand_couple(self.visit(left), self.visit(right)),
        ])
    }

    fn visit_release(
        &self,
        formula: &Formula,
        interval: &Interval,
        left: &Formula,
        right: &Formula,
        parent_upper: &Option<i32>,
    ) -> Formula {
        let f_part = Formula::f(
            Interval {
                lower: 0,
                upper: interval.lower,
            },
            None,
            self.visit(left),
        );
        Formula::or(vec![
            f_part,
            formula
                .with_interval(interval.clone())
                .with_parent_upper(*parent_upper)
                .with_operand_couple(self.visit(left), self.visit(right)),
        ])
    }
}

pub struct FlatTransformer;
impl RecursiveFormulaTransformer for FlatTransformer {
    fn visit_and(&self, formula: &Formula, ops: &[Formula]) -> Formula {
        formula.with_operands(
            ops.iter()
                .map(|op| self.visit(op))
                .flat_map(|flat_op| {
                    if let Formula::And(inner_ops) = &flat_op {
                        inner_ops.clone()
                    } else {
                        vec![flat_op]
                    }
                })
                .collect(),
        )
    }

    fn visit_or(&self, formula: &Formula, ops: &[Formula]) -> Formula {
        formula.with_operands(
            ops.iter()
                .map(|op| self.visit(op))
                .flat_map(|flat_op| {
                    if let Formula::Or(inner_ops) = &flat_op {
                        inner_ops.clone()
                    } else {
                        vec![flat_op]
                    }
                })
                .collect(),
        )
    }
}

struct ShiftBoundsTransformer;
impl RecursiveFormulaTransformer for ShiftBoundsTransformer {
    fn visit_globally(
        &self,
        formula: &Formula,
        interval: &Interval,
        phi: &Formula,
        _parent_upper: &Option<i32>,
    ) -> Formula {
        let new_phi = self.visit(phi);
        if let Some(shift) = new_phi.get_shift() {
            formula
                .with_interval(interval.shift_right(shift))
                .with_operand(ShiftBackwardTransformer(shift).visit(&new_phi))
        } else {
            formula.with_operand(new_phi)
        }
    }

    fn visit_finally(
        &self,
        formula: &Formula,
        interval: &Interval,
        phi: &Formula,
        _parent_upper: &Option<i32>,
    ) -> Formula {
        let new_phi = self.visit(phi);
        if let Some(shift) = new_phi.get_shift() {
            formula
                .with_interval(interval.shift_right(shift))
                .with_operand(ShiftBackwardTransformer(shift).visit(&new_phi))
        } else {
            formula.with_operand(new_phi)
        }
    }

    fn visit_until(
        &self,
        formula: &Formula,
        interval: &Interval,
        left: &Formula,
        right: &Formula,
        _parent_upper: &Option<i32>,
    ) -> Formula {
        let new_left = self.visit(left);
        let new_right = self.visit(right);
        if let Some(shift) = new_left.get_shift().min(new_right.get_shift()) {
            formula
                .with_interval(interval.shift_right(shift))
                .with_operand_couple(
                    ShiftBackwardTransformer(shift).visit(&new_left),
                    ShiftBackwardTransformer(shift).visit(&new_right),
                )
        } else {
            formula.with_operand_couple(new_left, new_right)
        }
    }

    fn visit_release(
        &self,
        formula: &Formula,
        interval: &Interval,
        left: &Formula,
        right: &Formula,
        _parent_upper: &Option<i32>,
    ) -> Formula {
        let new_left = self.visit(left);
        let new_right = self.visit(right);
        if let Some(shift) = new_left.get_shift().min(new_right.get_shift()) {
            formula
                .with_interval(interval.shift_right(shift))
                .with_operand_couple(
                    ShiftBackwardTransformer(shift).visit(&new_left),
                    ShiftBackwardTransformer(shift).visit(&new_right),
                )
        } else {
            formula.with_operand_couple(new_left, new_right)
        }
    }
}

struct ShiftBackwardTransformer(i32);
impl RecursiveFormulaTransformer for ShiftBackwardTransformer {
    fn visit_globally(
        &self,
        formula: &Formula,
        interval: &Interval,
        _phi: &Formula,
        _parent_upper: &Option<i32>,
    ) -> Formula {
        formula.with_interval(interval.shift_left(self.0).unwrap())
    }

    fn visit_finally(
        &self,
        formula: &Formula,
        interval: &Interval,
        _phi: &Formula,
        _parent_upper: &Option<i32>,
    ) -> Formula {
        formula.with_interval(interval.shift_left(self.0).unwrap())
    }

    fn visit_until(
        &self,
        formula: &Formula,
        interval: &Interval,
        _left: &Formula,
        _right: &Formula,
        _parent_upper: &Option<i32>,
    ) -> Formula {
        formula.with_interval(interval.shift_left(self.0).unwrap())
    }

    fn visit_release(
        &self,
        formula: &Formula,
        interval: &Interval,
        _left: &Formula,
        _right: &Formula,
        _parent_upper: &Option<i32>,
    ) -> Formula {
        formula.with_interval(interval.shift_left(self.0).unwrap())
    }
}

struct ShiftForwardTransformer(i32);
impl RecursiveFormulaTransformer for ShiftForwardTransformer {
    fn visit_globally(
        &self,
        formula: &Formula,
        interval: &Interval,
        _phi: &Formula,
        _parent_upper: &Option<i32>,
    ) -> Formula {
        formula.with_interval(interval.shift_right(self.0))
    }

    fn visit_finally(
        &self,
        formula: &Formula,
        interval: &Interval,
        _phi: &Formula,
        _parent_upper: &Option<i32>,
    ) -> Formula {
        formula.with_interval(interval.shift_right(self.0))
    }

    fn visit_until(
        &self,
        formula: &Formula,
        interval: &Interval,
        _left: &Formula,
        _right: &Formula,
        _parent_upper: &Option<i32>,
    ) -> Formula {
        formula.with_interval(interval.shift_right(self.0))
    }

    fn visit_release(
        &self,
        formula: &Formula,
        interval: &Interval,
        _left: &Formula,
        _right: &Formula,
        _parent_upper: &Option<i32>,
    ) -> Formula {
        formula.with_interval(interval.shift_right(self.0))
    }

    fn visit_not(&self, formula: &Formula, _inner: &Formula) -> Formula {
        Formula::f(
            Interval {
                lower: self.0,
                upper: self.0,
            },
            None,
            formula.clone(),
        )
    }

    fn visit_leaf(&self, formula: &Formula, _expr: &Expr) -> Formula {
        Formula::f(
            Interval {
                lower: self.0,
                upper: self.0,
            },
            None,
            formula.clone(),
        )
    }
}

pub struct DupeFormula;
impl RecursiveFormulaTransformer for DupeFormula {
    fn visit_leaf(&self, _formula: &Formula, expr: &Expr) -> Formula {
        Formula::prop(Expr::from_expr(expr.kind.clone()))
    }
}

pub struct FormulaSimplifier;
impl RecursiveFormulaTransformer for FormulaSimplifier {
    fn visit_and(&self, formula: &Formula, ops: &[Formula]) -> Formula {
        fn merge_globally_in_and(input: Vec<Formula>) -> Vec<Formula> {
            let mut to_remove = BTreeSet::new();
            let mut map: BTreeMap<usize, Interval> = BTreeMap::new();

            for (idx, op) in input.iter().enumerate() {
                if let Formula::G { interval, phi, .. } = op {
                    let mut found = None;
                    for (rep_idx, rep_formula) in input.iter().enumerate() {
                        if rep_idx >= idx {
                            break;
                        }
                        if let Formula::G { phi: rep_phi, .. } = rep_formula
                            && rep_phi.eq_structural(phi)
                        {
                            found = Some(rep_idx);
                            break;
                        }
                    }

                    match found {
                        Some(rep_idx) => {
                            if let Some(current) = map.get_mut(&rep_idx) {
                                if current.intersects(interval) || current.contiguous(interval) {
                                    *current = current.union(interval);
                                    to_remove.insert(idx);
                                }
                            } else if let Formula::G {
                                interval: rep_int, ..
                            } = &input[rep_idx]
                                && (rep_int.intersects(interval) || rep_int.contiguous(interval))
                            {
                                map.insert(rep_idx, rep_int.union(interval));
                                to_remove.insert(idx);
                            }
                        }
                        None => {
                            map.insert(idx, interval.clone());
                        }
                    }
                }
            }

            let mut new_operands = input.clone();
            for (idx, merged_interval) in &map {
                new_operands[*idx] = new_operands[*idx].with_interval(merged_interval.clone());
            }

            new_operands
                .into_iter()
                .enumerate()
                .filter(|(i, _)| !to_remove.contains(i))
                .map(|(_, f)| f)
                .collect()
        }

        // 1. recursively simplify children
        let mut flat: Vec<Formula> = Vec::new();
        for op in ops {
            let v = self.visit(op);
            // flatten nested ANDs
            match v {
                Formula::And(inner) => flat.extend(inner),
                other => flat.push(other),
            }
        }

        // 2. remove duplicates (A && A = A)
        let mut unique: Vec<Formula> = Vec::new();
        for op in flat {
            if !unique.iter().any(|u| u.eq_structural(&op)) {
                unique.push(op);
            }
        }

        // 3. check annihilators and identities

        // false in any operand ⇒ false
        for u in &unique {
            if let Formula::Prop(e) = u
                && let ExprKind::False = e.kind
            {
                return Formula::prop(Expr::false_expr());
            }
        }

        // remove all "true" operands (A && true = A)
        unique.retain(|u| {
            if let Formula::Prop(e) = u
                && let ExprKind::True = e.kind
            {
                return false;
            }
            true
        });

        // 4. contradiction: A && !A = false
        for u in &unique {
            if let Formula::Not(inner) = u
                && unique.iter().any(|x| x.eq_structural(inner))
            {
                return Formula::prop(Expr::false_expr());
            }
        }

        // 5. simplify interaction with disjunctive structures
        let mut reduced: Vec<Formula> = Vec::new();
        for u in &unique {
            match u {
                // (A && (A || B)) → A
                Formula::Or(disjuncts) => {
                    if disjuncts
                        .iter()
                        .any(|d| unique.iter().any(|a| a.eq_structural(d)))
                    {
                        continue; // redundant OR
                    }
                }
                // (A && F[0,u](A)) → A
                Formula::F { interval, phi, .. } if interval.lower == 0 => {
                    if unique.iter().any(|a| a.eq_structural(phi)) {
                        continue; // redundant F[0,u](A)
                    }
                }
                _ => {}
            }
            reduced.push(u.clone());
        }

        // 6. merge temporal operators
        reduced = merge_globally_in_and(reduced);

        // 7. collapse trivial results
        if reduced.is_empty() {
            return Formula::prop(Expr::true_expr()); // empty conjunction = true
        }
        if reduced.len() == 1 {
            return reduced[0].clone();
        }

        // 8. rebuild normalized formula
        formula.with_operands(reduced)
    }

    fn visit_or(&self, formula: &Formula, ops: &[Formula]) -> Formula {
        fn merge_globally_in_or(input: Vec<Formula>) -> Vec<Formula> {
            let mut map: BTreeMap<usize, Interval> = BTreeMap::new();
            let mut to_remove = BTreeSet::new();

            for (idx, op) in input.iter().enumerate() {
                if let Formula::G { phi, interval, .. } = op {
                    for (j, prev) in input.iter().enumerate().take(idx) {
                        if let Formula::G {
                            phi: phi_j,
                            interval: int_j,
                            ..
                        } = prev
                            && phi.eq_structural(phi_j)
                        {
                            if interval.contains(int_j) {
                                to_remove.insert(idx);
                            } else if int_j.contains(interval) {
                                to_remove.insert(j);
                                map.insert(idx, interval.clone());
                            }
                            break;
                        }
                    }
                    map.entry(idx).or_insert(interval.clone());
                }
            }

            input
                .into_iter()
                .enumerate()
                .filter(|(i, _)| !to_remove.contains(i))
                .map(|(_, f)| f)
                .collect()
        }

        // 1. recursively simplify children
        let mut flat: Vec<Formula> = Vec::new();
        for op in ops {
            let v = self.visit(op);
            // flatten nested ORs
            match v {
                Formula::Or(inner) => flat.extend(inner),
                other => flat.push(other),
            }
        }

        // 2. remove duplicates (A || A = A)
        let mut unique: Vec<Formula> = Vec::new();
        for op in flat {
            if !unique.iter().any(|u| u.eq_structural(&op)) {
                unique.push(op);
            }
        }

        // 3. annihilators and identities
        // true in any operand ⇒ true
        for u in &unique {
            if let Formula::Prop(e) = u
                && let ExprKind::True = e.kind
            {
                return Formula::prop(Expr::true_expr());
            }
        }

        // remove all "false" operands (A || false = A)
        unique.retain(|u| {
            if let Formula::Prop(e) = u
                && let ExprKind::False = e.kind
            {
                return false;
            }
            true
        });

        // 4. tautology: A || !A = true
        for u in &unique {
            if let Formula::Not(inner) = u
                && unique.iter().any(|x| x.eq_structural(inner))
            {
                return Formula::prop(Expr::true_expr());
            }
        }

        // 5. absorption with conjunctive or temporal structures
        let mut reduced: Vec<Formula> = Vec::new();
        for u in &unique {
            match u {
                // (A || (A && B)) → A
                Formula::And(conjuncts) => {
                    if conjuncts
                        .iter()
                        .any(|c| unique.iter().any(|a| a.eq_structural(c)))
                    {
                        continue; // redundant AND
                    }
                }
                // (A || G[0,u](A)) → A
                Formula::G { interval, phi, .. } => {
                    if interval.lower == 0 && unique.iter().any(|a| a.eq_structural(phi)) {
                        continue; // redundant G[0,u](A)
                    }
                }
                _ => {}
            }
            reduced.push(u.clone());
        }

        // 6. merge temporal operators
        reduced = merge_globally_in_or(reduced);

        // 7. collapse trivial results
        if reduced.is_empty() {
            return Formula::prop(Expr::false_expr());
        }
        if reduced.len() == 1 {
            return reduced[0].clone();
        }

        // 8. rebuild normalized formula
        formula.with_operands(reduced)
    }

    fn visit_globally(
        &self,
        formula: &Formula,
        interval: &Interval,
        phi: &Formula,
        parent_upper: &Option<i32>,
    ) -> Formula {
        // 1. simplify inner formula recursively
        let new_phi = self.visit(phi);

        // 2. constant folding
        if let Formula::Prop(e) = &new_phi {
            match e.kind {
                ExprKind::True => return Formula::prop(Expr::true_expr()),
                ExprKind::False => return Formula::prop(Expr::false_expr()),
                _ => {}
            }
        }

        // 3. collapse nested G:  G[a,b](G[c,d](φ)) → G[a+c, b+d](φ)
        if let Formula::G {
            interval: inner_i,
            phi: inner_phi,
            ..
        } = &new_phi
        {
            let summed = Interval {
                lower: interval.lower + inner_i.lower,
                upper: interval.upper + inner_i.upper,
            };
            return self.visit(&Formula::g(summed, *parent_upper, *inner_phi.clone()));
        }

        // 4. degenerate intervals
        if interval.lower == 0 && interval.upper == 0 {
            return new_phi; // G[0,0](φ) ≡ φ
        }

        if interval.lower == interval.upper {
            return ShiftForwardTransformer(interval.lower).visit(&new_phi);
        }

        // 5. rebuild
        formula.with_operand(new_phi)
    }

    fn visit_finally(
        &self,
        formula: &Formula,
        interval: &Interval,
        phi: &Formula,
        parent_upper: &Option<i32>,
    ) -> Formula {
        // 1. simplify inner formula recursively
        let new_phi = self.visit(phi);

        // 2. constant folding
        if let Formula::Prop(e) = &new_phi {
            match e.kind {
                ExprKind::True => return Formula::prop(Expr::true_expr()),
                ExprKind::False => return Formula::prop(Expr::false_expr()),
                _ => {}
            }
        }

        // 3. collapse nested F:  F[a,b](F[c,d](φ)) → F[a+c, b+d](φ)
        if let Formula::F {
            interval: inner_i,
            phi: inner_phi,
            ..
        } = &new_phi
        {
            let summed = Interval {
                lower: interval.lower + inner_i.lower,
                upper: interval.upper + inner_i.upper,
            };
            return self.visit(&Formula::f(summed, *parent_upper, *inner_phi.clone()));
        }

        // 4. degenerate intervals
        if interval.lower == 0 && interval.upper == 0 {
            return new_phi; // F[0,0](φ) ≡ φ
        }

        if interval.lower == interval.upper {
            return ShiftForwardTransformer(interval.lower).visit(&new_phi);
        }

        // 5. rebuild
        formula.with_operand(new_phi)
    }

    fn visit_until(
        &self,
        formula: &Formula,
        interval: &Interval,
        left: &Formula,
        right: &Formula,
        parent_upper: &Option<i32>,
    ) -> Formula {
        // 1. recursively simplify both operands
        let new_left = self.visit(left);
        let new_right = self.visit(right);

        // 2. constant folding: left side simplifications
        if let Formula::Prop(e) = &new_left {
            match e.kind {
                // true U[a,b](f) = F[a,b](f)
                ExprKind::True => {
                    return self.visit(&Formula::f(interval.clone(), *parent_upper, new_right));
                }

                // false U[a,b](f) = F[a,a](f)
                ExprKind::False => {
                    let reduced = Interval {
                        lower: interval.lower,
                        upper: interval.lower,
                    };
                    return self.visit(&Formula::f(reduced, *parent_upper, new_right));
                }

                _ => {}
            }
        }

        // 3. constant folding: right side simplifications
        if let Formula::Prop(e) = &new_right {
            match e.kind {
                // f U[a,b](true) = true
                ExprKind::True => return Formula::prop(Expr::true_expr()),
                // f U[a,b](false) = false
                ExprKind::False => return Formula::prop(Expr::false_expr()),
                _ => {}
            }
        }

        // a U[a,b](!a) = F[a,b](!a)
        if let Formula::Not(inner) = &new_right
            && inner.eq_structural(&new_left)
        {
            return self.visit(&Formula::f(
                interval.clone(),
                *parent_upper,
                new_right.clone(),
            ));
        }

        // !a U[a,b](a) = F[a,b](a)
        if let Formula::Not(inner) = &new_left
            && inner.eq_structural(&new_right)
        {
            return self.visit(&Formula::f(
                interval.clone(),
                *parent_upper,
                new_right.clone(),
            ));
        }

        // 4. degenerate intervals
        if interval.lower == 0 && interval.upper == 0 {
            // U[0,0](φ, ψ) ≡ ψ
            return new_right;
        }

        if interval.lower == interval.upper {
            return ShiftForwardTransformer(interval.lower).visit(&new_right);
        }

        // 5. rebuild
        formula.with_operand_couple(new_left, new_right)
    }

    fn visit_release(
        &self,
        formula: &Formula,
        interval: &Interval,
        left: &Formula,
        right: &Formula,
        parent_upper: &Option<i32>,
    ) -> Formula {
        let new_left = self.visit(left);
        let new_right = self.visit(right);

        // constant folding on right operand
        if let Formula::Prop(e) = &new_right {
            match e.kind {
                // f R[a,b](true) = true
                ExprKind::True => return Formula::prop(Expr::true_expr()),
                // f R[a,b](false) = false
                ExprKind::False => return Formula::prop(Expr::false_expr()),
                _ => {}
            }
        }

        // constant folding on left operand
        if let Formula::Prop(e) = &new_left {
            match e.kind {
                // true R[a,b](f) = F[a,a] f
                ExprKind::True => {
                    return self.visit(&Formula::f(
                        Interval {
                            lower: interval.lower,
                            upper: interval.lower,
                        },
                        *parent_upper,
                        new_right,
                    ));
                }
                // false R[a,b](f) = G[a,b] f
                ExprKind::False => {
                    return self.visit(&Formula::g(interval.clone(), *parent_upper, new_right));
                }
                _ => {}
            }
        }

        // !a R[a,b](a) = G[a,b](a)
        if let Formula::Not(inner) = &new_left
            && inner.eq_structural(&new_right)
        {
            return self.visit(&Formula::g(
                interval.clone(),
                *parent_upper,
                new_right.clone(),
            ));
        }

        // a R[a,b](!a) = G[a,b](!a)
        if let Formula::Not(inner) = &new_right
            && inner.eq_structural(&new_left)
        {
            return self.visit(&Formula::g(
                interval.clone(),
                *parent_upper,
                new_right.clone(),
            ));
        }

        formula.with_operand_couple(new_left, new_right)
    }
}

impl Formula {
    fn get_shift(&self) -> Option<i32> {
        match &self {
            Formula::And(operands) | Formula::Or(operands) => operands
                .iter()
                .map(super::Formula::get_shift)
                .min()
                .unwrap_or(None),
            Formula::Imply {
                left,
                right,
                not_left,
            } => left
                .get_shift()
                .min(right.get_shift())
                .min(not_left.get_shift()),
            _ => self.lower_bound(),
        }
    }
}

impl Node {
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
