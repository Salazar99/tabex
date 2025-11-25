use std::collections::{BTreeMap, BTreeSet};

use crate::{
    formula::{AExpr, Expr, ExprKind, Formula, Interval, VariableName},
    sat::tableau::node::Node,
};

#[cfg(test)]
mod tests;

#[derive(Debug)]
pub struct Signature {
    pub map: BTreeMap<VariableName, Vec<(Interval, Vec<usize>)>>,
}

impl Signature {
    #[must_use]
    pub fn new(node: &Node) -> Self {
        let mut raw_map: BTreeMap<VariableName, Vec<(Interval, usize)>> = BTreeMap::new();

        for formula in &node.operands {
            if formula.kind.get_interval().is_none() {
                continue;
            }

            let mut vars = BTreeMap::new();
            let ctx = Interval {
                lower: node.current_time,
                upper: node.current_time,
            };
            collect_variables(&formula.kind, ctx, &mut vars, true);

            for (name, intervals) in vars {
                for interval in intervals {
                    raw_map
                        .entry(name.clone())
                        .or_default()
                        .push((interval, formula.id));
                }
            }
        }

        let mut map = BTreeMap::new();
        for (name, intervals) in raw_map {
            map.insert(name, merge_intervals(intervals));
        }

        Self { map }
    }

    pub fn problematic(&self) -> bool {
        self.map
            .values()
            .any(|intervals| intervals.iter().any(|interval| interval.1.len() > 1))
    }
}

fn collect_variables(
    formula: &Formula,
    ctx: Interval,
    vars: &mut BTreeMap<VariableName, Vec<Interval>>,
    is_top_level: bool,
) {
    match formula {
        Formula::Prop(expr) => {
            collect_expr_variables(expr, ctx, vars);
        }
        Formula::And(ops) | Formula::Or(ops) => {
            for op in ops {
                collect_variables(op, ctx.clone(), vars, is_top_level);
            }
        }
        Formula::Not(op) => {
            collect_variables(op, ctx, vars, is_top_level);
        }
        Formula::Imply {
            left,
            right,
            not_left,
        } => {
            collect_variables(left, ctx.clone(), vars, is_top_level);
            collect_variables(right, ctx.clone(), vars, is_top_level);
            collect_variables(not_left, ctx, vars, is_top_level);
        }
        Formula::G { interval, phi } | Formula::F { interval, phi } => {
            let new_ctx = if is_top_level {
                Interval {
                    lower: interval.lower.max(ctx.lower),
                    upper: interval.upper,
                }
            } else {
                Interval {
                    lower: ctx.lower + interval.lower,
                    upper: ctx.upper + interval.upper,
                }
            };
            collect_variables(phi, new_ctx, vars, false);
        }
        Formula::U {
            interval,
            left,
            right,
        }
        | Formula::R {
            interval,
            left,
            right,
        } => {
            let new_ctx = if is_top_level {
                Interval {
                    lower: interval.lower.max(ctx.lower),
                    upper: interval.upper,
                }
            } else {
                Interval {
                    lower: ctx.lower + interval.lower,
                    upper: ctx.upper + interval.upper,
                }
            };
            collect_variables(left, new_ctx.clone(), vars, false);
            collect_variables(right, new_ctx, vars, false);
        }
    }
}

fn collect_expr_variables(
    expr: &Expr,
    ctx: Interval,
    vars: &mut BTreeMap<VariableName, Vec<Interval>>,
) {
    match &expr.kind {
        ExprKind::Atom(name) => {
            vars.entry(name.clone()).or_default().push(ctx);
        }
        ExprKind::Rel { left, right, .. } => {
            collect_aexpr_variables(left, ctx.clone(), vars);
            collect_aexpr_variables(right, ctx, vars);
        }
        _ => {}
    }
}

fn collect_aexpr_variables(
    expr: &AExpr,
    ctx: Interval,
    vars: &mut BTreeMap<VariableName, Vec<Interval>>,
) {
    match expr {
        AExpr::Var(name) => {
            vars.entry(name.clone()).or_default().push(ctx);
        }
        AExpr::BinOp { left, right, .. } => {
            collect_aexpr_variables(left, ctx.clone(), vars);
            collect_aexpr_variables(right, ctx, vars);
        }
        AExpr::Abs(inner) => {
            collect_aexpr_variables(inner, ctx, vars);
        }
        _ => {}
    }
}

fn merge_intervals(items: Vec<(Interval, usize)>) -> Vec<(Interval, Vec<usize>)> {
    if items.is_empty() {
        return Vec::new();
    }

    let mut points = BTreeSet::new();
    for (interval, _) in &items {
        points.insert(interval.lower);
        points.insert(interval.upper + 1);
    }

    let sorted_points: Vec<i32> = points.into_iter().collect();
    let mut result: Vec<(Interval, Vec<usize>)> = Vec::new();

    for i in 0..sorted_points.len() - 1 {
        let start = sorted_points[i];
        let end = sorted_points[i + 1] - 1;

        if start > end {
            continue;
        }

        let current_interval = Interval {
            lower: start,
            upper: end,
        };
        let mut ids = Vec::new();

        for (interval, id) in &items {
            if interval.lower <= start && interval.upper >= end {
                ids.push(*id);
            }
        }

        if !ids.is_empty() {
            ids.sort_unstable();
            ids.dedup();

            // Try to merge with previous if ids are same and contiguous
            if let Some((last_interval, last_ids)) = result.last_mut() {
                if *last_ids == ids && last_interval.upper + 1 == start {
                    last_interval.upper = end;
                    continue;
                }
            }

            result.push((current_interval, ids));
        }
    }

    result
}
