use nom::{
    branch::alt,
    bytes::complete::{tag, tag_no_case},
    character::{complete::{alpha1, char, digit1, space0}},
    combinator::{map, map_res, opt, recognize},
    multi::{fold_many0, many0},
    sequence::{delimited, pair, preceded},
    IResult,
    Parser
};
use num_rational::Ratio;
use std::{fs, path::Path, str::FromStr};

use crate::formula::*;

fn parse_arith_op(input: &str) -> IResult<&str, ArithOp> {
    alt((
        map(char('+'), |_| ArithOp::Add),
        map(char('-'), |_| ArithOp::Sub),
    )).parse(input)
}

fn parse_rel_op(input: &str) -> IResult<&str, RelOp> {
    alt((
        map(tag("<="), |_| RelOp::Le),
        map(tag("<"), |_| RelOp::Lt),
        map(tag(">="), |_| RelOp::Ge),
        map(tag(">"), |_| RelOp::Gt),
        map(tag("=="), |_| RelOp::Eq),
        map(tag("!="), |_| RelOp::Ne),
    )).parse(input)
}

fn parse_aexpr(input: &str) -> IResult<&str, AExpr> {
    fn aexpr_term(input: &str) -> IResult<&str, AExpr> {
        alt((
            // Number
            map(
                parse_decimal,
                |v| AExpr::Num(v)
            ),
            // Variable
            map(
                recognize(pair(alpha1, many0(alt((alpha1, digit1, tag("_")))))),
                |s: &str| AExpr::Var(s.into())
            ),
            // Absolute value: |expr|
            map(
                delimited(char('|'), parse_aexpr, char('|')),
                |expr| AExpr::Abs(Box::new(expr))
            ),
            // Parenthesized expression
            delimited(char('('), parse_aexpr, char(')')),
        ))
        .parse(input)
    }
    let (input, init) = aexpr_term(input)?;

    fold_many0(
        pair(delimited(space0, parse_arith_op, space0), aexpr_term),
        move || init.clone(),
        |acc, (op, rhs)| AExpr::BinOp { op, left: Box::new(acc), right: Box::new(rhs) }
    ).parse(input)
}

fn parse_expr(input: &str) -> IResult<&str, Expr> {
    alt((
        // Relational expression: left op right (must come before Atom)
        map(
            (
                parse_aexpr,
                nom::character::complete::space0,
                parse_rel_op,
                nom::character::complete::space0,
                parse_aexpr
            ),
            |(left, _, op, _, right)| Expr::Rel { op, left, right }
        ),
        // Atom: identifier (comes last as fallback)
        map(
            recognize(pair(alpha1, many0(alt((alpha1, digit1, tag("_")))))),
            |s: &str| Expr::Atom(s.into())
        ),
    )).parse(input)
}

fn parse_interval(input: &str) -> IResult<&str, Interval> {
    map(
        delimited(
            char('['),
            (
                preceded(space0, parse_interval_number),
                preceded(delimited(space0, char(','), space0), parse_interval_number)
            ),
            preceded(space0, char(']'))
        ),
        |(lower, upper)| Interval { lower, upper }
    ).parse(input)
}

fn parse_interval_number(input: &str) -> IResult<&str, i32> {
    map_res(digit1, |s: &str| i32::from_str(s)).parse(input)
}

fn parse_number(input: &str) -> IResult<&str, i64> {
    map_res(
        recognize(pair(opt(char('-')), digit1)),
        |s: &str| i64::from_str(s)
    ).parse(input)
}

fn parse_decimal(input: &str) -> IResult<&str, Ratio<i64>> {
    map(
        pair(
            parse_number,
            opt(
                pair(
                    char('.'),
                    map_res(digit1, |s: &str| i64::from_str(s))
                )
            )
        ),
        |(int_part, frac_part)| {
            match frac_part {
                Some((_, frac_val)) => {
                    let scale = 10i64.pow(frac_val.to_string().len() as u32);
                    Ratio::new(int_part * scale + frac_val, scale)
                }
                None => Ratio::from_integer(int_part),
            }
        }
    ).parse(input)
}

pub fn parse_formula(input: &str) -> IResult<&str, Formula> {

    fn parse_implication(input: &str) -> IResult<&str, Formula> {
        let (input, init) = parse_logical_or(input)?;
        
        fold_many0(
            pair(preceded(space0, tag("->")), preceded(space0, parse_implication)),
            move || init.clone(),
            |acc, (_, right)| Formula::Imply(Box::new(acc), Box::new(right))
        ).parse(input)
    }

    fn parse_logical_or(input: &str) -> IResult<&str, Formula> {
        let (input, init) = parse_logical_and(input)?;
        
        fold_many0(
            pair(preceded(space0, tag("||")), preceded(space0, parse_logical_and)),
            move || init.clone(),
            |acc, (_, right)| Formula::Or(vec![acc, right])
        ).parse(input)
    }

    fn parse_logical_and(input: &str) -> IResult<&str, Formula> {
        let (input, init) = parse_binary_temporal(input)?;
        
        fold_many0(
            pair(preceded(space0, tag("&&")), preceded(space0, parse_binary_temporal)),
            move || init.clone(),
            |acc, (_, right)| Formula::And(vec![acc, right])
        ).parse(input)
    }

    fn parse_binary_temporal(input: &str) -> IResult<&str, Formula> {
        let (input, init) = parse_formula_term(input)?;
        
        fold_many0(
            pair(
                alt((
                    map(pair(preceded(space0, tag("U")), parse_interval), |(_, interval)| ("U", Some(interval))),
                    map(pair(preceded(space0, tag("R")), parse_interval), |(_, interval)| ("R", Some(interval))),
                )),
                preceded(space0, parse_formula_term)
            ),
            move || init.clone(),
            |acc, ((op, interval), right)| match op {
                "U" => Formula::U { interval: interval.unwrap(), left: Box::new(acc), right: Box::new(right), parent_upper: None },
                "R" => Formula::R { interval: interval.unwrap(), left: Box::new(acc), right: Box::new(right), parent_upper: None },
                _ => panic!(), // Should not happen
            }
        ).parse(input)
    }

    fn parse_formula_term(input: &str) -> IResult<&str, Formula> {
        alt((
            map(tag_no_case("true"), |_| Formula::True),
            map(tag_no_case("false"), |_| Formula::False),
            map(
                (
                    tag("G"),
                    parse_interval,
                    space0,
                    parse_formula_term
                ),
                |(_, interval, _, phi)| Formula::G {
                    interval: interval,
                    phi: Box::new(phi),
                    parent_upper: None,
                }
            ),
            map(
                (
                    tag("F"),
                    parse_interval,
                    space0,
                    parse_formula_term
                ),
                |(_, interval, _, phi)| Formula::F {
                    interval: interval,
                    phi: Box::new(phi),
                    parent_upper: None,
                }
            ),
            map(
                (
                    char('O'),
                    space0,
                    parse_formula_term
                ),
                |(_, _, phi)| Formula::O(Box::new(phi))
            ),
            map(
                (
                    char('!'),
                    space0,
                    parse_formula_term
                ),
                |(_, _, phi)| Formula::Not(Box::new(phi))
            ),
            delimited(char('('), parse_formula, char(')')),
            map(parse_expr, Formula::Prop),
        )).parse(input)
    }
    
    parse_implication(input)
}

pub fn parse_stl_file(filename: &str) {
    let path = Path::new("resources").join(filename);
    println!("\n=== Parsing {} ===", filename);

    match fs::read_to_string(&path) {
        Ok(content) => {
            for (line_num, line) in content.lines().enumerate() {
                let line = line.trim();
                if line.is_empty() || line.starts_with('#') {
                    continue; // Skip empty lines and comments
                }

                println!("\nLine {}: {}", line_num + 1, line);
                match parse_formula(line) {
                    Ok((remaining, formula)) => {
                        println!("  ✓ Parsed: {:?}", formula);
                        if !remaining.is_empty() {
                            println!("  ⚠ Remaining: '{}'", remaining);
                        }
                    }
                    Err(e) => {
                        println!("  ✗ Parse error: {:?}", e);
                    }
                }
            }
        }
        Err(e) => {
            println!("Error reading file {}: {}", filename, e);
        }
    }
}
