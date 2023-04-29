use ruff_text_size::{TextLen, TextRange, TextSize};

use ruff_diagnostics::{Diagnostic, Violation};
use ruff_macros::{derive_message_formats, violation};
use ruff_python_ast::newlines::Line;
use ruff_python_ast::whitespace::leading_space;

/// ## What it does
/// Checks for the presence tabs in indentation.
///
/// ## Why is this bad?
/// [PEP 8] recommends spaces are used for indentation.
///
/// > Spaces are the preferred indentation method.
/// >
/// > Tabs should be used solely to remain consistent with code that is
/// already indented with tabs.
/// >
/// > Python disallows mixing tabs and spaces for indentation.
///
/// ## Example - Where `--->` represents a tab:
/// ```python
/// def foo(x):
/// --->return x * 2
/// ```
///
/// Use instead:
/// ```python
/// def foo(x):
///     return x * 2
/// ```
///
/// [PEP 8]: https://peps.python.org/pep-0008/#tabs-or-spaces
#[violation]
pub struct TabIndentation;

impl Violation for TabIndentation {
    #[derive_message_formats]
    fn message(&self) -> String {
        format!("Indentation contains tabs")
    }
}

/// W191
pub(crate) fn tab_indentation(line: &Line, string_ranges: &[TextRange]) -> Option<Diagnostic> {
    let indent = leading_space(line);
    if let Some(tab_index) = indent.find('\t') {
        let tab_offset = line.start() + TextSize::try_from(tab_index).unwrap();

        let string_range_index = string_ranges.binary_search_by(|range| {
            if tab_offset < range.start() {
                std::cmp::Ordering::Greater
            } else if range.contains(tab_offset) {
                std::cmp::Ordering::Equal
            } else {
                std::cmp::Ordering::Less
            }
        });

        // If the tab character is within a multi-line string, abort.
        if string_range_index.is_ok() {
            None
        } else {
            Some(Diagnostic::new(
                TabIndentation,
                TextRange::at(line.start(), indent.text_len()),
            ))
        }
    } else {
        None
    }
}
