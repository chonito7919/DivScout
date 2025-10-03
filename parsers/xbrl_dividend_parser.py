"""
XBRL Dividend Parser
Extracts dividend data from SEC Company Facts API JSON
Enhanced with confidence scoring and better annual total detection
"""

from datetime import datetime, timedelta
from typing import List, Dict, Optional, Tuple
import statistics
import logging

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class XBRLDividendParser:
    """
    Parse dividend data from XBRL company facts JSON
    with enhanced data quality checks and confidence scoring
    """
    
    def __init__(self):
        # XBRL tags that contain dividend data
        self.dividend_tags = [
            'CommonStockDividendsPerShareDeclared',
            'CommonStockDividendsPerShareCashPaid',
            'DividendsCommonStock',
            'DividendsCommonStockCash'
        ]
        
        # Data quality thresholds
        self.max_reasonable_dividend = 50.0
        self.min_reasonable_dividend = 0.01
        self.annual_total_threshold = 3.0  # Flag if >3x median
        
        # Company-specific overrides (CIK -> settings)
        self.company_overrides = {
            '0000018230': {'max_reasonable': 10.0},  # Caterpillar
            '0000027419': {'fiscal_year_end_month': 1},  # Target
        }
    
    def parse_company_facts(self, facts_json: dict, cik: Optional[str] = None) -> List[Dict]:
        """
        Extract all dividend data from company facts JSON
        
        Args:
            facts_json: Response from SEC companyfacts API
            cik: Company CIK for company-specific rules
            
        Returns:
            List of dividend dictionaries with confidence scores
        """
        if not facts_json:
            return []
        
        # Extract CIK from facts if not provided
        if not cik:
            cik = str(facts_json.get('cik', '')).zfill(10)
        
        dividends = []
        
        # Get US-GAAP facts
        us_gaap = facts_json.get('facts', {}).get('us-gaap', {})
        
        if not us_gaap:
            logger.warning(f"No US-GAAP facts found for CIK {cik}")
            return []
        
        # Process each dividend tag
        for tag in self.dividend_tags:
            if tag in us_gaap:
                tag_dividends = self._parse_dividend_tag(us_gaap[tag], tag)
                dividends.extend(tag_dividends)
        
        if not dividends:
            return []
        
        # Stage 1: Basic deduplication
        unique_dividends = self._deduplicate_basic(dividends)
        
        # Stage 2: Detect and filter annual totals
        filtered_dividends = self._filter_annual_totals(unique_dividends, cik)
        
        # Stage 3: Add confidence scores
        scored_dividends = self._add_confidence_scores(filtered_dividends, cik)
        
        # Sort by date
        scored_dividends.sort(key=lambda d: d['ex_dividend_date'])
        
        return scored_dividends
    
    def _parse_dividend_tag(self, tag_data: dict, tag_name: str) -> List[Dict]:
        """
        Parse a single XBRL tag's data
        """
        dividends = []
        
        # Get units (usually USD/shares or USD)
        units = tag_data.get('units', {})
        
        # Try USD/shares first (per-share amounts)
        for unit_type in ['USD/shares', 'USD', 'pure']:
            if unit_type not in units:
                continue
            
            for fact in units[unit_type]:
                dividend = self._parse_fact(fact, tag_name, unit_type)
                if dividend:
                    dividends.append(dividend)
        
        return dividends
    
    def _parse_fact(self, fact: dict, tag_name: str, unit_type: str) -> Optional[Dict]:
        """
        Parse a single XBRL fact into a dividend record
        """
        try:
            # Extract value
            val = fact.get('val')
            if not val or val <= 0:
                return None
            
            # Convert to per-share if needed
            amount = float(val)
            
            # For tags like DividendsCommonStock (total $), skip
            if unit_type == 'USD' and 'PerShare' not in tag_name:
                return None
            
            # Extract dates
            start_date = fact.get('start')
            end_date = fact.get('end')
            filed_date = fact.get('filed')
            form = fact.get('form')
            
            if not end_date:
                return None
            
            # Parse dates
            ex_date = datetime.strptime(end_date, '%Y-%m-%d').date()
            
            # Calculate period duration (important for detecting cumulative)
            period_type = 'instant'
            period_days = 0
            
            if start_date:
                start = datetime.strptime(start_date, '%Y-%m-%d').date()
                period_days = (ex_date - start).days
                
                if 80 <= period_days <= 100:
                    period_type = 'quarterly'
                elif 165 <= period_days <= 185:
                    period_type = 'semi_annual'
                elif 355 <= period_days <= 375:
                    period_type = 'annual'
                else:
                    period_type = 'other'
            
            # Extract fiscal period info
            fiscal_year = fact.get('fy')
            fiscal_period = fact.get('fp')  # Q1, Q2, Q3, Q4, FY
            
            # Skip obvious annual totals
            if fiscal_period == 'FY':
                logger.debug(f"Skipping FY entry: ${amount} on {ex_date}")
                return None
            
            # Skip entries with no fiscal period from 10-K (often annual)
            if not fiscal_period and form in ['10-K', '8-K']:
                logger.debug(f"Skipping no-period entry from {form}: ${amount}")
                return None
            
            # Map fiscal period to quarter
            fiscal_quarter = None
            if fiscal_period:
                quarter_map = {'Q1': 1, 'Q2': 2, 'Q3': 3, 'Q4': 4}
                fiscal_quarter = quarter_map.get(fiscal_period)
            
            # Get filing info
            accession = fact.get('accn')
            
            return {
                'amount': round(amount, 4),
                'ex_dividend_date': ex_date,
                'fiscal_year': fiscal_year,
                'fiscal_quarter': fiscal_quarter,
                'fiscal_period': fiscal_period,
                'frequency': 'quarterly' if fiscal_quarter else None,
                'dividend_type': 'cash',
                'source_tag': tag_name,
                'source_form': form,
                'source_accession': accession,
                'filed_date': filed_date,
                'period_type': period_type,
                'period_days': period_days,
                'start_date': start_date,
                'end_date': end_date,
                'declaration_date': None,
                'record_date': None,
                'payment_date': None,
                'confidence': 1.0  # Will be adjusted later
            }
            
        except (ValueError, KeyError, TypeError) as e:
            logger.error(f"Error parsing fact: {e}")
            return None
    
    def _deduplicate_basic(self, dividends: List[Dict]) -> List[Dict]:
        """
        Basic deduplication - keep smallest amount per date
        """
        if not dividends:
            return []
        
        by_date = {}
        
        for div in dividends:
            date = div['ex_dividend_date']
            
            if date not in by_date:
                by_date[date] = []
            by_date[date].append(div)
        
        unique = []
        for date, divs in by_date.items():
            if len(divs) == 1:
                unique.append(divs[0])
                continue
            
            # Keep the smallest amount (likely quarterly, not cumulative)
            amounts = sorted([d['amount'] for d in divs])
            smallest = amounts[0]
            
            # Allow some tolerance (up to 2.5x smallest)
            candidates = [d for d in divs if d['amount'] <= smallest * 2.5]
            
            if not candidates:
                candidates = [min(divs, key=lambda d: d['amount'])]
            
            # Prefer 'Declared' over 'Paid' tags
            candidates_sorted = sorted(candidates, key=lambda d: (
                d['amount'],
                0 if 'Declared' in d['source_tag'] else 1
            ))
            
            unique.append(candidates_sorted[0])
        
        return unique
    
    def _filter_annual_totals(self, dividends: List[Dict], cik: Optional[str] = None) -> List[Dict]:
        """
        Advanced filtering to detect and remove annual totals
        """
        if len(dividends) < 4:
            return dividends
        
        # Group by year
        by_year = {}
        for div in dividends:
            year = div['ex_dividend_date'].year
            if year not in by_year:
                by_year[year] = []
            by_year[year].append(div)
        
        filtered = []
        
        for year, year_divs in by_year.items():
            if len(year_divs) <= 4:
                # Normal quarterly pattern or less
                filtered.extend(year_divs)
                continue
            
            # More than 4 dividends in a year - likely has annual total
            amounts = sorted([d['amount'] for d in year_divs])
            
            # Method 1: Statistical outlier detection
            if len(amounts) >= 4:
                q1 = amounts[len(amounts)//4]
                q3 = amounts[3*len(amounts)//4]
                iqr = q3 - q1
                
                if iqr > 0:
                    upper_bound = q3 + 1.5 * iqr
                    
                    # Filter outliers
                    year_filtered = [d for d in year_divs if d['amount'] <= upper_bound]
                    
                    if year_filtered:
                        filtered.extend(year_filtered)
                        removed = len(year_divs) - len(year_filtered)
                        if removed > 0:
                            logger.info(f"Removed {removed} outliers from year {year}")
                        continue
            
            # Method 2: Look for amount that's ~4x the median
            median = statistics.median(amounts)
            
            for div in year_divs:
                ratio = div['amount'] / median
                
                # Check if this looks like an annual total
                if 3.5 <= ratio <= 4.5 and div.get('fiscal_period') in [None, 'Q4']:
                    logger.info(f"Skipping likely annual total: ${div['amount']} on {div['ex_dividend_date']}")
                    continue
                
                # Check if it's unreasonably high
                if ratio > 5.0:
                    logger.info(f"Skipping very high amount: ${div['amount']} ({ratio:.1f}x median)")
                    continue
                
                filtered.append(div)
        
        return filtered
    
    def _add_confidence_scores(self, dividends: List[Dict], cik: Optional[str] = None) -> List[Dict]:
        """
        Add confidence scores to each dividend based on various factors
        """
        if not dividends:
            return []
        
        # Calculate baseline statistics
        amounts = [d['amount'] for d in dividends]
        
        if len(amounts) >= 4:
            median = statistics.median(amounts)
            mean = statistics.mean(amounts)
            
            try:
                stdev = statistics.stdev(amounts)
                cv = stdev / mean if mean > 0 else 0
            except:
                stdev = 0
                cv = 0
        else:
            median = mean = amounts[0] if amounts else 0
            stdev = cv = 0
        
        # Score each dividend
        for div in dividends:
            confidence = 1.0
            reasons = []
            
            # Check amount reasonableness
            if div['amount'] > self.max_reasonable_dividend:
                confidence *= 0.5
                reasons.append(f"Very high amount (${div['amount']})")
            
            if div['amount'] < self.min_reasonable_dividend:
                confidence *= 0.7
                reasons.append(f"Very low amount (${div['amount']})")
            
            # Check against median
            if median > 0:
                ratio = div['amount'] / median
                
                if ratio > 3.0:
                    confidence *= 0.6
                    reasons.append(f"High vs median ({ratio:.1f}x)")
                elif ratio > 2.0:
                    confidence *= 0.8
                    reasons.append(f"Above median ({ratio:.1f}x)")
                elif ratio < 0.5:
                    confidence *= 0.8
                    reasons.append(f"Below median ({ratio:.1f}x)")
            
            # Check period type
            if div.get('period_type') == 'annual':
                confidence *= 0.3
                reasons.append("Annual period duration")
            elif div.get('period_type') == 'semi_annual':
                confidence *= 0.5
                reasons.append("Semi-annual period")
            
            # Check fiscal period
            if not div.get('fiscal_period'):
                confidence *= 0.9
                reasons.append("No fiscal period")
            
            # Check source
            if div.get('source_form') == '10-K' and not div.get('fiscal_quarter'):
                confidence *= 0.8
                reasons.append("From 10-K without quarter")
            
            # Company-specific adjustments
            if cik and cik in self.company_overrides:
                overrides = self.company_overrides[cik]
                
                if 'max_reasonable' in overrides:
                    if div['amount'] > overrides['max_reasonable']:
                        confidence *= 0.7
                        reasons.append("Company-specific high amount")
            
            # Set final values
            div['confidence'] = round(confidence, 3)
            div['confidence_reasons'] = reasons
            div['needs_review'] = confidence < 0.8
        
        return dividends
    
    def get_summary_statistics(self, dividends: List[Dict]) -> Dict:
        """
        Calculate summary statistics for a set of dividends
        """
        if not dividends:
            return {'status': 'No dividends found'}
        
        amounts = [d['amount'] for d in dividends]
        confidences = [d.get('confidence', 1.0) for d in dividends]
        
        stats = {
            'count': len(dividends),
            'amount_min': min(amounts),
            'amount_max': max(amounts),
            'amount_mean': statistics.mean(amounts),
            'amount_median': statistics.median(amounts),
            'confidence_mean': statistics.mean(confidences),
            'needs_review_count': sum(1 for d in dividends if d.get('needs_review', False)),
            'date_range': f"{min(d['ex_dividend_date'] for d in dividends)} to {max(d['ex_dividend_date'] for d in dividends)}"
        }
        
        if len(amounts) >= 2:
            stats['amount_stdev'] = statistics.stdev(amounts)
            stats['coefficient_variation'] = stats['amount_stdev'] / stats['amount_mean'] if stats['amount_mean'] > 0 else 0
        
        # Detect pattern
        if stats.get('coefficient_variation', 0) < 0.1:
            stats['pattern'] = 'Very stable'
        elif stats.get('coefficient_variation', 0) < 0.3:
            stats['pattern'] = 'Stable'
        elif stats.get('coefficient_variation', 0) < 0.5:
            stats['pattern'] = 'Variable'
        else:
            stats['pattern'] = 'Highly variable'
        
        return stats


if __name__ == "__main__":
    # Test with sample XBRL data
    print("Testing Enhanced XBRL Dividend Parser...")
    print("="*70)
    
    # Sample company facts structure
    sample_facts = {
        'cik': 320193,
        'entityName': 'Apple Inc.',
        'facts': {
            'us-gaap': {
                'CommonStockDividendsPerShareDeclared': {
                    'label': 'Common Stock, Dividends, Per Share, Declared',
                    'units': {
                        'USD/shares': [
                            {
                                'end': '2024-03-30',
                                'val': 0.24,
                                'accn': '0000320193-24-000055',
                                'fy': 2024,
                                'fp': 'Q2',
                                'form': '10-Q',
                                'filed': '2024-05-02'
                            },
                            {
                                'end': '2023-12-30',
                                'val': 0.24,
                                'accn': '0000320193-24-000010',
                                'fy': 2024,
                                'fp': 'Q1',
                                'form': '10-Q',
                                'filed': '2024-02-01'
                            },
                            {
                                'end': '2023-12-30',
                                'val': 0.96,  # Potential annual total
                                'accn': '0000320193-24-000010',
                                'fy': 2023,
                                'fp': 'FY',
                                'form': '10-K',
                                'filed': '2024-02-01'
                            }
                        ]
                    }
                }
            }
        }
    }
    
    parser = XBRLDividendParser()
    dividends = parser.parse_company_facts(sample_facts, '0000320193')
    
    print(f"\nParsed {len(dividends)} dividends:")
    for div in dividends:
        print(f"\n  ${div['amount']:.4f} on {div['ex_dividend_date']}")
        print(f"    Confidence: {div['confidence']:.2f}")
        if div.get('confidence_reasons'):
            print(f"    Reasons: {', '.join(div['confidence_reasons'])}")
        print(f"    Review needed: {div.get('needs_review', False)}")
    
    # Show statistics
    stats = parser.get_summary_statistics(dividends)
    print(f"\nStatistics:")
    for key, value in stats.items():
        print(f"  {key}: {value}")
    
    print("\n" + "="*70)