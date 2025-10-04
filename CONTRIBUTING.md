# Contributing to DivScout

Thank you for your interest in contributing to DivScout! This document provides guidelines for contributing to the project.

## Important: Project Purpose and Scope

Before contributing, please understand:

- **This project is for educational and informational purposes only**
- **This is NOT a financial advice tool**
- **Contributors agree their work will NOT be used to provide financial advice**
- All contributions must comply with SEC data usage policies and Fair Access guidelines
- Data accuracy and code quality are critical priorities

## Code of Conduct

### Our Standards

- Be respectful and professional in all interactions
- Focus on constructive feedback and collaboration
- Accept that code reviews may request significant changes
- Acknowledge that data accuracy is more important than feature velocity
- Understand that not all feature requests align with the project's scope

### Unacceptable Behavior

- Promoting this tool as providing financial advice
- Using this project to distribute financial recommendations
- Circumventing SEC rate limits or access policies
- Adding features that scrape data in violation of SEC terms
- Harassment or unprofessional conduct

## What We're Looking For

### High Priority Contributions

- **Bug fixes** - especially data quality or parsing issues
- **Test coverage** - additional test cases with real company data
- **Documentation improvements** - clearer explanations, better examples
- **Data quality enhancements** - better detection of annual totals, edge cases
- **CIK expansion** - adding more ticker-to-CIK mappings
- **Performance improvements** - faster parsing, better database queries

### Medium Priority Contributions

- **Error handling** - better error messages and recovery
- **Logging improvements** - more detailed audit trails
- **Admin tools** - better data review and cleanup utilities

### Low Priority / May Be Rejected

- **UI/Web interface** - project focuses on data extraction, not presentation (consider contributing to [divscout-web](https://github.com/chonito7919/divscout-web) instead)
- **Real-time features** - not aligned with XBRL data source capabilities
- **Prediction/ML features** - outside project scope, implies financial advice
- **Alternative data sources** - must use official SEC APIs only

## How to Contribute

### 1. Fork and Clone

```bash
git clone https://github.com/chonito7919/DivScout.git
cd DivScout
```

### 2. Set Up Development Environment

```bash
# Create virtual environment
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Set up .env file (see README.md for required variables)
cp .env.example .env  # Edit with your values
```

### 3. Create a Branch

```bash
git checkout -b feature/your-feature-name
# or
git checkout -b fix/issue-description
```

Use descriptive branch names:
- `feature/add-more-ciks`
- `fix/annual-total-detection`
- `docs/improve-setup-instructions`

### 4. Make Your Changes

#### Code Style

- Follow existing code style and conventions
- Use clear, descriptive variable and function names
- Add docstrings to all functions and classes
- Keep functions focused and single-purpose
- Avoid overly clever or obscure code

#### Comments

- Explain **why**, not **what** (the code shows what)
- Document edge cases and assumptions
- Reference SEC documentation when relevant
- Mark TODOs with clear descriptions

Example:
```python
# Good: Explains why
# Skip fiscal year entries as they represent annual totals, not individual dividends
if fiscal_period == 'FY':
    continue

# Bad: Explains what (obvious from code)
# Check if fiscal period equals FY
if fiscal_period == 'FY':
    continue
```

#### Testing Requirements

**All code changes must include tests.**

- Add test cases for new features
- Add regression tests for bug fixes
- Test with real company data when possible (use known stable companies like AAPL, JNJ, KO)
- Include both positive and negative test cases
- Document expected vs. actual behavior

Example test companies:
- **AAPL** (Apple): Clean quarterly dividends, good for baseline testing
- **JNJ** (Johnson & Johnson): Long dividend history
- **KO** (Coca-Cola): Stable pattern
- **O** (Realty Income): Monthly dividends (edge case)

#### Database Changes

If you modify database structure or queries:
- Update schema documentation in comments
- Test with real PostgreSQL database
- Consider migration path for existing data
- Document any new tables or columns

### 5. Test Your Changes

```bash
# Test individual components
python parsers/xbrl_dividend_parser.py
python sec_edgar_client.py
python db_connection.py

# Test with real companies (requires database and SEC_USER_AGENT)
python main.py AAPL

# Run admin tools
python admin/admin_stats.py
```

**Important**: Do not commit test data or real company data to the repository.

### 6. Commit Your Changes

Write clear, descriptive commit messages:

```bash
# Good commit messages
git commit -m "Fix: Correctly filter annual totals when median is zero"
git commit -m "Add: Support for monthly dividend detection"
git commit -m "Docs: Clarify SEC_USER_AGENT requirement in setup"

# Bad commit messages
git commit -m "Fixed bug"
git commit -m "Updates"
git commit -m "WIP"
```

Follow conventional commit format:
- `Fix:` - Bug fixes
- `Add:` - New features
- `Update:` - Improvements to existing features
- `Docs:` - Documentation changes
- `Test:` - Test additions or fixes
- `Refactor:` - Code restructuring without functionality changes

### 7. Push and Create Pull Request

```bash
git push origin feature/your-feature-name
```

Then create a Pull Request on GitHub with:

**Required PR Information:**
- **Clear title** describing the change
- **Description** of what changed and why
- **Testing performed** - which companies, what scenarios
- **Related issues** - link to any related issue numbers
- **Breaking changes** - note if this changes existing behavior
- **Data quality impact** - how this affects accuracy/confidence scoring

**PR Template:**

```markdown
## Description
Brief description of changes

## Motivation
Why is this change needed?

## Testing
- [ ] Tested with AAPL
- [ ] Tested with JNJ
- [ ] Tested edge cases: [describe]
- [ ] Verified confidence scoring still works
- [ ] Checked for regressions

## Checklist
- [ ] Code follows project style
- [ ] Added/updated docstrings
- [ ] Added tests for new code
- [ ] Tested with real SEC data
- [ ] Updated documentation if needed
- [ ] No breaking changes (or documented if unavoidable)

## Data Quality Impact
How does this affect data accuracy/confidence?
```

### 8. Code Review Process

- Maintainers will review your PR
- Expect questions and change requests
- Be responsive to feedback
- Multiple review rounds are normal for data-critical code
- PRs may be rejected if they don't align with project scope

## Specific Contribution Guidelines

### Adding New CIKs

To add ticker-to-CIK mappings:

1. Verify CIK from official SEC sources
2. Add to `known_ciks` dict in `sec_edgar_client.py`
3. Test with `python main.py TICKER`
4. Include test results in PR

### Improving Data Quality

When improving parsing or filtering:

1. Document the issue with specific examples (company, date, amount)
2. Explain your detection logic
3. Test against 5+ companies to avoid overfitting
4. Show before/after confidence scores
5. Consider false positive rate

### Documentation Changes

- Keep README.md up to date with functionality changes
- Update CLAUDE.md if architecture changes
- Maintain accurate disclaimers about financial advice
- Use clear, professional language

## SEC API Usage Requirements

**All contributions must comply with SEC Fair Access policy:**

- Maximum 10 requests per second
- Proper User-Agent identification required
- No circumventing rate limits
- No bulk downloads without cause
- Respect SEC system availability

See: https://www.sec.gov/os/accessing-edgar-data

## Database Schema

Expected database tables (see `schema.sql` for full schema):

- `companies` - Company master data
- `dividend_events` - Dividend records with confidence scoring
- `data_collection_log` - Audit trail of scraping runs
- `data_sources` - Source tracking for data provenance
- `dividend_review_log` - Manual review audit trail

Set up the database with:
```bash
psql -U your_user -d your_database -f schema.sql
```

## Questions?

- **For bugs**: Open an issue with detailed reproduction steps
- **For features**: Open an issue to discuss before implementing
- **For questions**: Check existing issues or open a discussion

## License Agreement

By contributing, you agree that your contributions will be licensed under the Apache License 2.0, the same license as this project.

You also agree that:
- Your contributions are your original work
- You have the right to submit the contributions
- Your contributions will not be used to provide financial advice
- You understand this project is for educational/informational purposes only

## Thank You!

Your contributions help make this tool more accurate and useful for educational purposes. We appreciate your time and effort in improving DivScout!

---

**Remember**: This is not financial advice. This project is for educational and informational purposes only.
