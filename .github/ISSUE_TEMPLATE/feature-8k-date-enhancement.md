---
name: Enhancement - Parse 8-K Filings for Complete Dividend Dates
about: Add support for extracting declaration, record, and payment dates from 8-K filings
title: '[ENHANCEMENT] Parse 8-K filings for complete dividend dates'
labels: enhancement, data-quality, sec-api
assignees: ''
---

## Summary

Currently, DivScout extracts dividend data from SEC XBRL CompanyFacts API, which only provides period start/end dates. This means we only have approximate ex-dividend dates and are missing:
- Declaration dates (when the board announces the dividend)
- Record dates (shareholder eligibility cutoff)
- Payment dates (when dividend is actually paid)

This enhancement would add 8-K filing parsing to extract these complete date fields.

## Current Limitation

**XBRL CompanyFacts API provides:**
- ✅ Dividend amount
- ✅ Period end date (used as proxy for ex-dividend date)
- ✅ Fiscal period info
- ❌ Declaration date
- ❌ Record date
- ❌ Payment date

**Where the data exists:**
8-K filings (Item 8.01 "Other Events") typically contain press releases announcing dividends with all four dates.

## Proposed Solution

### Architecture

1. **Add 8-K Filing Parser** (`parsers/filing_8k_parser.py`)
   - Search for dividend-related 8-K filings
   - Extract text from filing HTML
   - Parse dates using regex patterns
   - Match to existing XBRL dividends by amount/approximate date

2. **Optional Enhancement Mode**
   - Add config flag: `ENABLE_8K_DATE_ENHANCEMENT`
   - Run as post-processing step after XBRL parsing
   - Update existing dividend records with found dates

3. **Matching Logic**
   - Match by: amount (±$0.01) + date within 30 days
   - Handle edge cases (stock splits, special dividends)
   - Log unmatched entries for review

### Implementation Steps

- [ ] Create `parsers/filing_8k_parser.py`
- [ ] Add 8-K search/download using SEC Submissions API
- [ ] Implement HTML/text extraction
- [ ] Write date extraction regex patterns
- [ ] Add matching logic to link 8-K dates to XBRL dividends
- [ ] Create config flag for opt-in enhancement
- [ ] Update database schema if needed
- [ ] Add tests with known 8-K filings
- [ ] Update documentation

### Example 8-K Filing Structure

```
Item 8.01. Other Events

On [Declaration Date], the Board of Directors of [Company]
declared a quarterly cash dividend of $[Amount] per share.

The dividend is payable on [Payment Date] to shareholders
of record as of the close of business on [Record Date].

The ex-dividend date is expected to be [Ex-Dividend Date].
```

## Technical Challenges

1. **Varying formats**: 8-K filings are unstructured HTML/text, not standardized like XBRL
2. **False positives**: Not all 8-Ks are dividend announcements
3. **Performance**: Would need to fetch/parse many filings per company
4. **Date parsing**: Companies use different date formats
5. **Matching accuracy**: Need robust logic to match 8-K to XBRL dividends

## Alternative Approaches Considered

### Option A: Third-party APIs
- **Pros**: Clean structured data, all dates provided
- **Cons**: Violates "SEC data only" principle, rate limits, costs
- **Decision**: Rejected to maintain data source integrity

### Option B: Manual review workflow
- **Pros**: Most accurate, no parsing needed
- **Cons**: Not scalable, defeats automation purpose
- **Decision**: Could complement but not replace automated solution

### Option C: Keep current XBRL-only approach
- **Pros**: Simple, reliable, sufficient for most use cases
- **Cons**: Missing date fields
- **Decision**: Current implementation, this enhancement is optional

## Success Criteria

- [ ] Successfully parse 8-K filings for major dividend payers (AAPL, JNJ, KO)
- [ ] >90% match rate for 8-K dates to XBRL dividends
- [ ] <5% false positive rate
- [ ] Maintain SEC rate limit compliance (10 req/sec)
- [ ] Opt-in via config, doesn't break existing functionality
- [ ] Clear documentation of limitations

## Testing Plan

**Test companies:**
- AAPL (Apple) - consistent quarterly dividends
- JNJ (Johnson & Johnson) - long history
- KO (Coca-Cola) - stable pattern
- O (Realty Income) - monthly dividends

**Test cases:**
- Normal quarterly dividends
- Special/one-time dividends
- Dividend increases/decreases
- Companies with stock splits
- Edge case: missing 8-K for a dividend

## Documentation Updates

- [ ] README.md - update "Data Completeness" section
- [ ] CLAUDE.md - add 8-K parsing architecture notes
- [ ] config.py - add ENABLE_8K_DATE_ENHANCEMENT flag
- [ ] Example usage in docs

## Estimated Effort

**Core implementation**: 1-2 days
**Testing & refinement**: 1 day
**Documentation**: 2-3 hours

**Total**: ~3 days for basic working version

## Related Issues

- Closes #XX (if there's a specific request for this)
- Related to data quality improvements

## References

- SEC 8-K Filing Guide: https://www.sec.gov/files/form8-k.pdf
- EDGAR Search API: https://www.sec.gov/edgar/sec-api-documentation
- Example 8-K: https://www.sec.gov/cgi-bin/browse-edgar?action=getcompany&CIK=0000320193&type=8-K

## Questions for Discussion

1. Should this be on by default or opt-in?
2. What's acceptable performance overhead (extra API calls)?
3. Should we cache 8-K filings to avoid re-fetching?
4. How to handle conflicts (XBRL date vs 8-K date differ)?

## Priority

**Medium-Low** - Nice to have, but current XBRL implementation is functional

**Rationale**: Most dividend tracking/analysis only requires amount + ex-dividend date. Declaration/payment dates are supplementary information.
