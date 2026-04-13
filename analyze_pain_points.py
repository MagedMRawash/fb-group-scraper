#!/usr/bin/env python3
"""
Comprehensive Pain Point Analysis for Facebook Posts
Analyzes all JSON files to extract and quantify business pain points
"""

import json
import os
from collections import defaultdict, Counter
from datetime import datetime
import re

# Define the 20 pain point categories
PAIN_CATEGORIES = {
    "Marketing Effectiveness Collapse": [
        r"(?:marketing|ads|advertising|promotion|campaign|social media|facebook ads|google ads|ROAS|conversion)",
        r"(?:media buyer|digital marketing|growth marketing|lead generation)"
    ],
    "Payment Processing Barriers": [
        r"(?:payment gateway|payment processor|stripe|paypal|fawry|paymob|visa|mastercard)",
        r"(?:banking|credit card|debit card|transaction|settlement|payout)",
        r"(?:دفع|بوابة دفع|تحويل بنكي|بطاقة ائتمان)"
    ],
    "Finding Technical Talent": [
        r"(?:developer|programmer|software engineer|frontend|backend|full stack|mobile app|ios|android)",
        r"(?:co.?founder|CTO|technical.?founder|tech.?lead|software.?house)",
        r"(?:مطور|مبرمج|مهندس برمجيات|تطبيق|موبايل)",
        r"(?:talent|team building|hiring|recruitment|outsourcing)"
    ],
    "Customer Acquisition": [
        r"(?:customer acquisition|get clients|find customers|sales|leads|prospects)",
        r"(?:عميل|عملاء|مبيعات|عميل جديد|استقطاب عملاء)"
    ],
    "Cash Flow Management": [
        r"(?:cash flow|working capital|funding|investment|investor|capital|revenue)",
        r"(?:cashflow|liquidity|bootstrapping|self.?funded|profitable)",
        r"(?:تدفق نقدي|رأس مال|تمويل|مستثمر|استثمار)"
    ],
    "WhatsApp Automation Issues": [
        r"(?:whatsapp|wa|واتساب) (?:api|automation|bot|business|integration)",
        r"(?:chatbot|messaging|broadcast|bulk message)",
        r"(?:حظر|block|ban|restriction|limit)"
    ],
    "CRM Implementation Challenges": [
        r"(?:CRM|customer relationship management|customer database|client management)",
        r"(?:customer retention|churn|loyalty|lifecycle)",
        r"(?:إدارة علاقات العملاء|قاعدة بيانات|احتفاظ بالعملاء)"
    ],
    "Legal & Compliance Barriers": [
        r"(?:legal|compliance|regulation|license|permit|trademark|copyright)",
        r"(?:tax|taxation|vat|income tax|corporate tax|filing)",
        r"(?:company formation|incorporation|LLC|entity|structure)",
        r"(?:legal|قانوني|ترخيص|سجل تجاري|بطاقة ضريبية|ضريبة)"
    ],
    "Pricing Strategy Confusion": [
        r"(?:pricing|price strategy|pricing model|monetization|revenue model)",
        r"(?:how much to charge|price point|affordable|expensive|cheap)",
        r"(?:تسعير|استراتيجية التسعير|كم أبيع|السعر المناسب)"
    ],
    "Marketing Automation Needs": [
        r"(?:marketing automation|email marketing|automation tools|workflow|funnel)",
        r"(?:sequenced? email|drip campaign|lead nurturing)",
        r"(?:automate|scale|growth hack)"
    ],
    "Finding Product-Market Fit": [
        r"(?:product.?market fit|PMF|validation|market research|customer discovery)",
        r"(?:mvp|minimum viable product|prototype|testing|feedback)",
        r"(?:دراسة جدوى|تحقيق المنتج مع السوق|MVP|بروتوتايب)"
    ],
    "International Business Expansion": [
        r"(?:international|global|expansion|export|foreign market|cross.?border)",
        r"(?:Gulf|Saudi|UAE|Kuwait|Qatar|Bahrain|Oman)",
        r"(?:الخليج|السعودية|الإمارات|الكويت|قطر|البحرين|عمان)",
        r"(?:currency exchange|multi.?currency|USD|EUR|GBP)"
    ],
    "Team Management Difficulties": [
        r"(?:team management|employee management|HR|human resources|remote team)",
        r"(?:productivity|time tracking|performance management|KPI)",
        r"(?:إدارة الفريق|الموظفين|الإنتاجية|تتبع الوقت)"
    ],
    "Customer Retention Issues": [
        r"(?:customer retention|customer loyalty|repeat purchase|lifetime value|CLV)",
        r"(?:churn rate|retention rate|customer satisfaction|NPS)",
        r"(?:احتفاظ بالعميل|ولاء العملاء|قيمة العميل|معدل التسرب)"
    ],
    "Technical Implementation": [
        r"(?:technical implementation|integration|API|SDK|plugin|extension)",
        r"(?:web development|app development|software development|coding)",
        r"(?:تنفيذ تقني|تطوير برمجي|دمج|واجهة برمجة)"
    ],
    "Business Operations Inefficiencies": [
        r"(?:operations|operational efficiency|process|workflow|SOP|procedures)",
        r"(?:scalability|scaling|growth pains|growing pains)",
        r"(?:العمليات|الكفاءة التشغيلية|الإجراءات|العمليات)"
    ],
    "Funding & Capital Access": [
        r"(?:funding|capital|investment|fundraising|venture capital|angel investor)",
        r"(?:grant|loan|debt financing|equity|valuation)",
        r"(?:تمويل|قرض|استثمار|رأس مال|منحة|صندوق)"
    ],
    "Social Media Marketing Effectiveness": [
        r"(?:social media|Instagram|Facebook|LinkedIn|Twitter|TikTok|content marketing)",
        r"(?:influencer|content creator|brand awareness|engagement)",
        r"(?:سوشيال ميديا|إنستجرام|فيسبوك|لينكد إن|محتوى|مؤثر)"
    ],
    "Sales Process Optimization": [
        r"(?:sales process|sales funnel|pipeline|deal closing|conversion rate)",
        r"(?:B2B sales|enterprise sales|consultative selling|sales training)",
        r"(?:عملية البيع|قمع المبيعات|إغلاق الصفقة|معدل التحويل)"
    ],
    "Data Management & Analytics": [
        r"(?:data analytics|business intelligence|reporting|dashboard|metrics)",
        r"(?:Google Analytics|data visualization|KPI|performance tracking)",
        r"(?:تحليل البيانات|تقارير|مقاييس الأداء|لوحة تحكم)"
    ]
}

def analyze_sentiment(text):
    """
    Analyze the sentiment and urgency of a post
    Returns: severity score (1-10)
    """
    urgency_keywords = [
        "urgent", "help", "need", "problem", "issue", "challenge",
        "struggling", "stuck", "blocked", "can't", "unable",
        "please", "desperately", "asap", "immediately", "emergency",
        "حاجة", "مشكلة", "عاجل", "محتاج", "عندى مشكلة",
        "فشل", "عاطل", "توقفت", "ما بيرفعش", "مشتغلش"
    ]

    severity_keywords = [
        "critical", "severe", "major", "serious", "breaking",
        "disaster", "catastrophe", "emergency", "crisis",
        "خطير", "حرج", "كارثة", "أزمة", "انهيار"
    ]

    text_lower = text.lower()

    urgency_count = sum(1 for keyword in urgency_keywords if keyword in text_lower)
    severity_count = sum(1 for keyword in severity_keywords if keyword in text_lower)

    # Base score + urgency + severity indicators
    score = 3 + (urgency_count * 1.5) + (severity_count * 2)

    return min(int(score), 10)  # Cap at 10

def detect_business_segment(text):
    """
    Detect business segment from post text
    Returns: 'freelancer', 'startup', 'sme', or 'unknown'
    """
    text_lower = text.lower()

    freelancer_indicators = [
        "freelancer", "freelance", "self-employed", "solo", "independent",
        "freelance", "أعمل حر", "فريلانسر", "مستقل", "عمل خاص"
    ]

    startup_indicators = [
        "startup", "startup", "founder", "co-founder", "venture",
        "MVP", "product-market fit", "seed stage", "pre-seed",
        "ستارت أب", "مؤسس", "مؤسس مشارك", "مرحلة MVP"
    ]

    sme_indicators = [
        "SME", "small business", "medium business", "company", "established",
        "years in business", "existing business", "ongoing business",
        "شركة", "بيزنس قائم", "لنا سنوات خبرة", "عملنا"
    ]

    freelancer_score = sum(1 for ind in freelancer_indicators if ind in text_lower)
    startup_score = sum(1 for ind in startup_indicators if ind in text_lower)
    sme_score = sum(1 for ind in sme_indicators if ind in text_lower)

    scores = {
        'freelancer': freelancer_score,
        'startup': startup_score,
        'sme': sme_score
    }

    max_score = max(scores.values())
    if max_score == 0:
        return 'unknown'

    # Return the segment with highest score
    for segment, score in scores.items():
        if score == max_score:
            return segment

    return 'unknown'

def extract_pain_points(text):
    """
    Extract pain points from text using category patterns
    Returns: list of detected pain point categories
    """
    detected_pains = []

    for category, patterns in PAIN_CATEGORIES.items():
        for pattern in patterns:
            if re.search(pattern, text, re.IGNORECASE):
                detected_pains.append(category)
                break  # Only count each category once per post

    return detected_pains

def analyze_file(file_path):
    """
    Analyze a single JSON file
    """
    with open(file_path, 'r', encoding='utf-8') as f:
        data = json.load(f)

    posts = data.get('posts', [])
    results = []

    for post in posts:
        text = post.get('text', '')
        if not text:
            continue

        pain_points = extract_pain_points(text)
        if not pain_points:
            continue

        severity = analyze_sentiment(text)
        segment = detect_business_segment(text)

        # Extract engagement metrics
        likes = post.get('likes', '0')
        comments = post.get('comments', '0')
        shares = post.get('shares', '0')

        # Convert Arabic numerals to English
        def convert_arabic_numeral(num_str):
            if isinstance(num_str, int):
                return num_str
            arabic_to_english = {
                '٠': '0', '١': '1', '٢': '2', '٣': '3', '٤': '4',
                '٥': '5', '٦': '6', '٧': '7', '٨': '8', '٩': '9'
            }
            for arabic, english in arabic_to_english.items():
                num_str = num_str.replace(arabic, english)
            try:
                return int(num_str)
            except:
                return 0

        likes = convert_arabic_numeral(str(likes))
        comments = convert_arabic_numeral(str(comments))
        shares = convert_arabic_numeral(str(shares))
        total_engagement = likes + comments + shares

        # Extract timestamp if available
        timestamp = post.get('timestamp', '')

        results.append({
            'text': text[:200] + '...' if len(text) > 200 else text,
            'pain_points': pain_points,
            'severity': severity,
            'segment': segment,
            'likes': likes,
            'comments': comments,
            'shares': shares,
            'total_engagement': total_engagement,
            'timestamp': timestamp,
            'url': post.get('url', '')
        })

    return results

def main():
    """
    Main analysis function
    """
    output_dir = '/Users/admin/Desktop/LeanStartup_Group_Scraper/output'

    # Get all JSON files
    json_files = [f for f in os.listdir(output_dir) if f.startswith('lean_startup_posts') and f.endswith('.json')]
    json_files.sort()

    print(f"Found {len(json_files)} JSON files to analyze")
    print("="*80)

    # Analyze all files
    all_results = []
    for filename in json_files:
        file_path = os.path.join(output_dir, filename)
        print(f"Analyzing: {filename}")
        results = analyze_file(file_path)
        all_results.extend(results)

    print(f"\nTotal posts analyzed: {len(all_results)}")
    print("="*80)

    # Aggregate statistics
    pain_point_counts = Counter()
    pain_point_severity = defaultdict(list)
    pain_point_segments = defaultdict(lambda: Counter())
    pain_point_engagement = defaultdict(list)

    for result in all_results:
        for pain_point in result['pain_points']:
            pain_point_counts[pain_point] += 1
            pain_point_severity[pain_point].append(result['severity'])
            pain_point_segments[pain_point][result['segment']] += 1
            pain_point_engagement[pain_point].append(result['total_engagement'])

    # Calculate averages
    pain_point_avg_severity = {
        pain: sum(severities) / len(severities)
        for pain, severities in pain_point_severity.items()
    }

    pain_point_avg_engagement = {
        pain: sum(engagements) / len(engagements)
        for pain, engagements in pain_point_engagement.items()
    }

    # Print detailed results
    print("\n" + "="*80)
    print("COMPREHENSIVE PAIN POINT ANALYSIS")
    print("="*80)

    print(f"\nTOTAL POSTS WITH PAIN POINTS: {len(all_results)}")
    print(f"TOTAL MENTIONS: {sum(pain_point_counts.values())}")

    # Rank pain points by frequency
    ranked_pains = pain_point_counts.most_common()

    print("\n" + "="*80)
    print("TOP 20 PAIN POINTS BY FREQUENCY")
    print("="*80)
    print(f"{'Rank':<6} {'Pain Point':<40} {'Frequency':<12} {'Severity':<10} {'Engagement':<12}")
    print("-"*80)

    for rank, (pain_point, count) in enumerate(ranked_pains[:20], 1):
        avg_severity = pain_point_avg_severity.get(pain_point, 0)
        avg_engagement = pain_point_avg_engagement.get(pain_point, 0)
        print(f"{rank:<6} {pain_point:<40} {count:<12} {avg_severity:<10.2f} {avg_engagement:<12.2f}")

    # Segment analysis
    print("\n" + "="*80)
    print("PAIN POINTS BY BUSINESS SEGMENT")
    print("="*80)

    for segment in ['freelancer', 'startup', 'sme']:
        segment_counts = Counter()
        for pain, segments_counter in pain_point_segments.items():
            segment_counts[pain] = segments_counter[segment]

        if segment_counts:
            print(f"\n{segment.upper()} TOP PAIN POINTS:")
            print(f"{'Rank':<6} {'Pain Point':<40} {'Count':<10}")
            print("-"*56)

            for rank, (pain, count) in enumerate(segment_counts.most_common(5), 1):
                print(f"{rank:<6} {pain:<40} {count:<10}")

    # Save detailed results to JSON
    output_data = {
        'total_posts_analyzed': len(all_results),
        'total_mentions': sum(pain_point_counts.values()),
        'pain_points': {
            pain_point: {
                'frequency': count,
                'average_severity': pain_point_avg_severity.get(pain_point, 0),
                'average_engagement': pain_point_avg_engagement.get(pain_point, 0),
                'by_segment': {
                    segment: pain_point_segments[pain_point][segment]
                    for segment in ['freelancer', 'startup', 'sme']
                }
            }
            for pain_point, count in ranked_pains
        },
        'sample_posts': all_results[:20]  # Include sample posts
    }

    output_file = '/Users/admin/Desktop/LeanStartup_Group_Scraper/pain_point_analysis_results.json'
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(output_data, f, ensure_ascii=False, indent=2)

    print(f"\n\nDetailed results saved to: {output_file}")

    return output_data

if __name__ == '__main__':
    main()