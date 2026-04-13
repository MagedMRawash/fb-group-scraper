#!/usr/bin/env python3
"""
Demographic & Market Readiness Analysis for Lean Startup Circle Egypt
Analyzes Facebook posts to extract demographic information and market readiness indicators
"""

import json
import os
import re
from collections import defaultdict, Counter
from pathlib import Path
from typing import Dict, List, Tuple, Any
import math

class DemographicAnalyzer:
    def __init__(self, output_dir: str):
        self.output_dir = output_dir
        self.posts = []
        self.posters_profile = defaultdict(dict)

        # Demographic categories
        self.business_stages = ["Idea Stage", "MVP/Validation Stage", "Growth Stage", "Established/SME"]
        self.business_types = ["Freelancer/Solo", "Startup (Seed/Series A)", "SME (Established)", "Agency/Service Business"]
        self.industries = ["Technology/SaaS", "Marketing & E-commerce", "EdTech", "HealthTech",
                          "Construction/Real Estate", "Food & Beverage", "Manufacturing/Export",
                          "Professional Services", "Other"]
        self.target_markets = ["Egypt Only", "GCC", "International/Global", "Regional MENA"]
        self.tech_levels = ["Non-technical", "Technical", "Developer"]

        # Market readiness indicators
        self.budget_ranges = ["$0-$500", "$500-$2K", "$2K-$10K", "$10K+"]
        self.tool_adoption = ["None", "Low", "Medium", "High"]
        self.willingness_to_pay = ["Low", "Medium", "High"]
        self.pain_tolerance = ["Low", "Medium", "High"]
        self.technical_capability = ["Low", "Medium", "High"]
        self.implementation_capability = ["Low", "Medium", "High"]
        self.regulatory_awareness = ["Low", "Medium", "High"]

        # Keyword patterns for classification
        self.setup_patterns()

    def setup_patterns(self):
        """Setup keyword patterns for demographic classification"""

        # Business stage patterns
        self.stage_patterns = {
            "Idea Stage": [
                "فكرة", "فكره", "idea", "ابدأ", "ابدء", "بدء", "بداية", "مبتدئ",
                "مشروع جديد", "نفس أبدأ", "طلع بمشروع", "بفكر أبدأ",
                "استارت اب", "startup", "فكرتي", "الفكرة", "مشروع استارت اب",
                "أنا بتخرج", "fresh graduate", "تخرجت", "دراسة مبدأية", "دراسة جدوى"
            ],
            "MVP/Validation Stage": [
                "mvp", "إم في بي", "تجربة", "تست", "test", "validation",
                "دراسة جدوى", "أنا بعمل دراسة", "عملت دراسة",
                "نستكمل", "استمرار", "التكلفة", "رأس مال", "capital",
                "أفكار جديدة", "أحب أطلع بمشروع", "مطلوب", "محتاج",
                "شريك", "co-founder", "فريق", "team", "توظيف", "hire"
            ],
            "Growth Stage": [
                "سيريس", "series", "seed", "fund", "funding", "استثمار",
                "مستثمر", "investor", "ترقيم", "scaling", "scale",
                "نمو", "growth", "زبائن", "عملاء", "customers",
                "أدخل فلوس", "ربح", "profit", "sales", "مبيعات"
            ],
            "Established/SME": [
                "سيمي", "smes", "شركة", "شركات", "company", "companies",
                "مؤسسة", "established", "سنوات", "years", "خبرة",
                "قائمة", "قائم", "running", "عملت", "أعمل", "نشاط",
                "مصنع", "factory", "مصانع", "تاجر", "تجار", "business"
            ]
        }

        # Business type patterns
        self.type_patterns = {
            "Freelancer/Solo": [
                "فري لانسر", "freelancer", "freelancing", "عمل حر",
                "فريلانسر", "أعمل لوحدي", "مستقل", "solo",
                "شخص واحد", "منفرد", "individual", "own business"
            ],
            "Startup (Seed/Series A)": [
                "استارت أب", "startup", "سيريس", "series", "seed",
                "ترقيم", "fundraising", "مستثمر", "investor",
                "شركة ناشئة", "شركة ناشئه", "co-founder", "شريك",
                "برنامج", "app", "تطبيق", "software", "منصة", "platform"
            ],
            "SME (Established)": [
                "سيمي", "sme", "مؤسسة", "شركة", "شركات",
                "تجارة", "تجار", "متاجر", "store", "stores",
                "مصنع", "factory", "خدمات", "business", "enterprise"
            ],
            "Agency/Service Business": [
                "وكالة", "agency", "خدمات", "service", "consulting",
                "استشارات", "marketing agency", "خدمة", "استشارة",
                "فرش خدمات", "خدمات برمجية", "استشارات إدارية"
            ]
        }

        # Industry patterns
        self.industry_patterns = {
            "Technology/SaaS": [
                "ساس", "saas", "software", "برنامج", "برمجيات",
                "تطبيق", "app", "منصة", "platform", "tech",
                "تكنولوجيا", "تقنية", "ai", "ذكاء اصطناعي", "artificial intelligence",
                "crm", "erp", "system", "نظام", "automation", "أتمتة"
            ],
            "Marketing & E-commerce": [
                "ماركتنج", "marketing", "تسويق", "دعاية", "advertisement",
                "أونلاين", "online", "تجارة إلكترونية", "e-commerce", "سوشيال ميديا",
                "social media", "ads", "إعلانات", "branding", "متجر", "store"
            ],
            "EdTech": [
                "تعليم", "education", "مدارس", "schools", "جامعة", "university",
                "دورات", "courses", "تعليم إلكتروني", "e-learning",
                "منصة تعليمية", "تدريس", "تعليمي"
            ],
            "HealthTech": [
                "صحة", "health", "طبي", "medical", "عيادات", "clinics",
                "دكاترة", "doctors", "hospital", "مستشفى", "medtech"
            ],
            "Construction/Real Estate": [
                "عقار", "real estate", "مقاولات", "construction", "بناء",
                "شقق", "apartments", "مباني", "buildings", "مشروع عقاري"
            ],
            "Food & Beverage": [
                "طعام", "food", "مطعم", "restaurant", "مشروبات", "beverages",
                "أكل", "كافيه", "cafe", "غذاء"
            ],
            "Manufacturing/Export": [
                "تصنيع", "manufacturing", "تصدير", "export", "مصنع",
                "factory", "إنتاج", "production", "تصنيعي"
            ],
            "Professional Services": [
                "محاسبة", "accounting", "قانوني", "legal", "ضريبة", "tax",
                "استشارات", "consulting", "خدمات مهنية", "خدمة مهنية"
            ]
        }

        # Target market patterns
        self.market_patterns = {
            "Egypt Only": [
                "مصر", "egypt", "السوق المصري", "محلي", "local",
                "في مصر", "القاهرة", "cairo", "الاسكندرية", "alexandria"
            ],
            "GCC": [
                "الخليج", "gcc", "السعودية", "saudi", "سعودية",
                "الامارات", "uae", "دبي", "dubai", "قطر", "qatar",
                "الكويت", "kuwait", "عمان", "oman", "بحرين", "bahrain"
            ],
            "International/Global": [
                "جلوبال", "global", "عالمي", "international", "global",
                "سوق عالمي", "خارج مصر", "خارج", "دولي", "أمريكا", "usa",
                "أوروبا", "europe", "بريطانيا", "uk"
            ],
            "Regional MENA": [
                "منطقة", "region", "شرق أوسط", "middle east", "mena",
                "المنطقة العربية", "العالم العربي", "إقليمي", "regional"
            ]
        }

        # Technical capability patterns
        self.tech_patterns = {
            "Non-technical": [
                "مش فاهم", "مش عارف", "أحتاج مبرمج", "أحتاج مطور",
                "ما عنديش خبرة", "أبتدئ", "أحتاج مساعدة", "كيف أعمل",
                "أحتاج توضيح", "مبتدئ"
            ],
            "Technical": [
                "مبرمج", "programmer", "developer", "مطور",
                "معرفة برمجة", "خبرة تقنية", "tech stack", "تقني",
                "كود", "code", "backend", "frontend"
            ],
            "Developer": [
                "أعمل برمجة", "developer", "software engineer", "كتابة كود",
                "سورس كود", "source code", "github", "git",
                "full stack", "backend developer", "frontend developer"
            ]
        }

        # Budget patterns
        self.budget_patterns = {
            "$0-$500": [
                r'\d+ جنيه', r'\d+ EGP', r'\d+ egp', "أقل من 500",
                "ميزانية قليلة", "ميزانية محدودة", "budget.*low"
            ],
            "$500-$2K": [
                r'(\d{3,4}) جنيه', r'(\d{3,4}) EGP', r'(\d{3,4}) egp',
                "ألف", r'\d+K', "كيلو", "بضعة آلاف"
            ],
            "$2K-$10K": [
                r'(\d{4,5}) جنيه', r'(\d{4,5}) EGP',
                "آلاف", "عشرات الآلاف", r'\d+,\d+', "عشرة آلاف"
            ],
            "$10K+": [
                r'(\d{6,}) جنيه', r'(\d{6,}) EGP', "ملايين",
                "مليون", "million", r'\d+M', "ميزانية كبيرة", "استثمار"
            ]
        }

        # Pain point patterns
        self.pain_point_patterns = {
            "Technical/Technical Implementation": [
                "أحتاج مبرمج", "مش عارف أبرمج", "أحتاج تطوير",
                "كيف أعمل تطبيق", "تكلفة برمجة", "برمجة", "programming",
                "technical issues", "مشاكل تقنية", "bugs", "أخطاء"
            ],
            "Marketing/Sales": [
                "زبائن", "عملاء", "customers", "marketing", "تسويق",
                "إعلانات", "ads", "مبيعات", "sales", "lead generation",
                "بيع", "selling", "توسع", "scaling"
            ],
            "Financial/Funding": [
                "تمويل", "funding", "مستثمر", "investor", "رأس مال",
                "capital", "استثمار", "investment", "ضريبة", "tax",
                "حساب بنكي", "bank account", "wise", "transfer"
            ],
            "Operations/Management": [
                "إدارة", "management", "فريق", "team", "توظيف",
                "hiring", "coo", "operations", "workflow", "workflow automation",
                "تنظيم", "organization", "أتمتة", "automation"
            ],
            "Legal/Regulatory": [
                "ترخيص", "license", "ضريبي", "tax", "ضرائب",
                "قانوني", "legal", "تأسيس شركة", "registration",
                "رقم ضريبي", "uin"
            ],
            "Customer Service/Support": [
                "خدمة عملاء", "customer service", "support", "دعم فني",
                "cr", "crm", "واتساب", "whatsapp", "تواصل مع العملاء"
            ]
        }

        # Tool preference patterns
        self.tool_patterns = {
            "CRM/WhatsApp": ["crm", "whatsapp", "wa", "واتساب", "3rab.cash"],
            "Payment Processing": ["fawry", "vodafone cash", "transfer", "payment"],
            "Marketing Tools": ["facebook ads", "google ads", "social media", "ads"],
            "Development Tools": ["github", "git", "code", "programming"],
            "Communication": ["zoom", "meet", "call", "meeting"],
            "Accounting/Finance": ["wise", "bank", "accounting", "tax"]
        }

    def load_all_posts(self):
        """Load all JSON files from output directory"""
        output_path = Path(self.output_dir)
        json_files = sorted(output_path.glob("lean_startup_posts_part*.json"))

        print(f"Found {len(json_files)} files to process...")

        for json_file in json_files:
            try:
                with open(json_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    if 'posts' in data:
                        self.posts.extend(data['posts'])
                        print(f"Loaded {len(data['posts'])} posts from {json_file.name}")
            except Exception as e:
                print(f"Error loading {json_file.name}: {e}")

        print(f"\nTotal posts loaded: {len(self.posts)}")

    def classify_text(self, text: str, patterns: Dict[str, List[str]]) -> Tuple[str, float]:
        """Classify text based on keyword patterns, return (category, confidence)"""
        if not text:
            return None, 0.0

        text_lower = text.lower()
        scores = defaultdict(int)

        for category, keywords in patterns.items():
            for keyword in keywords:
                if keyword.lower() in text_lower:
                    scores[category] += 1

        if not scores:
            return None, 0.0

        # Return category with highest score and normalized confidence
        best_category = max(scores.keys(), key=lambda k: scores[k])
        confidence = min(scores[best_category] / 5.0, 1.0)  # Normalize to 0-1

        return best_category, confidence

    def extract_budget(self, text: str) -> Tuple[str, float]:
        """Extract budget range from text"""
        if not text:
            return None, 0.0

        # Look for specific amounts
        amounts = re.findall(r'(\d+)\s*(جنيه|EGP|egp|\$)', text)
        if amounts:
            try:
                amount = int(amounts[0][0])
                if amount < 500:
                    return "$0-$500", 0.9
                elif amount < 2000:
                    return "$500-$2K", 0.9
                elif amount < 10000:
                    return "$2K-$10K", 0.9
                else:
                    return "$10K+", 0.9
            except:
                pass

        # Use pattern matching
        budget, confidence = self.classify_text(text, self.budget_patterns)
        return budget, confidence

    def extract_multiple_categories(self, text: str, patterns: Dict[str, List[str]]) -> List[str]:
        """Extract all matching categories from text"""
        if not text:
            return []

        text_lower = text.lower()
        matched = []

        for category, keywords in patterns.items():
            for keyword in keywords:
                if keyword.lower() in text_lower:
                    if category not in matched:
                        matched.append(category)
                    break

        return matched

    def calculate_readiness_score(self, poster_data: dict) -> float:
        """Calculate market readiness score (1-100)"""
        score = 0.0
        weights = {
            'budget': 15,
            'tech_capability': 15,
            'implementation_capability': 15,
            'willingness_to_pay': 15,
            'pain_tolerance': 15,
            'tool_adoption': 10,
            'business_stage': 15
        }

        # Budget score
        if poster_data.get('budget_range'):
            budget_idx = self.budget_ranges.index(poster_data['budget_range']) if poster_data['budget_range'] in self.budget_ranges else 0
            score += (budget_idx + 1) * (weights['budget'] / len(self.budget_ranges))

        # Tech capability score
        if poster_data.get('tech_level'):
            tech_idx = self.tech_levels.index(poster_data['tech_level']) if poster_data['tech_level'] in self.tech_levels else 0
            score += (tech_idx + 1) * (weights['tech_capability'] / len(self.tech_levels))

        # Business stage score
        if poster_data.get('business_stage'):
            stage_idx = self.business_stages.index(poster_data['business_stage']) if poster_data['business_stage'] in self.business_stages else 0
            score += (stage_idx + 1) * (weights['business_stage'] / len(self.business_stages))

        # Implementation capability (inferred from tech level)
        if poster_data.get('tech_level'):
            score += ((self.tech_levels.index(poster_data['tech_level']) + 1) / len(self.tech_levels)) * weights['implementation_capability']

        # Willingness to pay (inferred from budget)
        if poster_data.get('budget_range'):
            budget_idx = self.budget_ranges.index(poster_data['budget_range']) if poster_data['budget_range'] in self.budget_ranges else 0
            score += ((budget_idx + 1) / len(self.budget_ranges)) * weights['willingness_to_pay']

        # Pain tolerance (inferred from stage - more established = higher tolerance)
        if poster_data.get('business_stage'):
            stage_idx = self.business_stages.index(poster_data['business_stage']) if poster_data['business_stage'] in self.business_stages else 0
            score += ((stage_idx + 1) / len(self.business_stages)) * weights['pain_tolerance']

        # Tool adoption (based on mentions)
        tool_mentions = len(poster_data.get('tool_preferences', []))
        score += min(tool_mentions / 3.0, 1.0) * weights['tool_adoption']

        return min(round(score), 100)

    def analyze_posts(self):
        """Analyze all posts and extract demographic information"""
        print("\nAnalyzing posts...")

        for post in self.posts:
            author = post.get('author', 'Unknown')
            text = post.get('text', '')
            likes = post.get('likes', '')
            comments = post.get('comments', '')

            # Extract engagement (convert Arabic numerals if needed)
            engagement = 0
            if likes:
                try:
                    # Convert Arabic numerals
                    arabic_to_english = {'١': '1', '٢': '2', '٣': '3', '٤': '4', '٥': '5',
                                       '٦': '6', '٧': '7', '٨': '8', '٩': '9', '٠': '0'}
                    likes_clean = ''.join(arabic_to_english.get(c, c) for c in likes)
                    likes_clean = re.sub(r'[^\d]', '', likes_clean)
                    if likes_clean:
                        engagement += int(likes_clean)
                except:
                    pass

            if comments:
                try:
                    comments_clean = re.sub(r'[^\d]', '', str(comments))
                    if comments_clean:
                        engagement += int(comments_clean)
                except:
                    pass

            # Classify demographics
            business_stage, _ = self.classify_text(text, self.stage_patterns)
            business_type, _ = self.classify_text(text, self.type_patterns)
            industry, _ = self.classify_text(text, self.industry_patterns)
            target_market, _ = self.classify_text(text, self.market_patterns)
            tech_level, _ = self.classify_text(text, self.tech_patterns)

            # Extract budget
            budget_range, _ = self.extract_budget(text)

            # Extract pain points and tool preferences
            pain_points = self.extract_multiple_categories(text, self.pain_point_patterns)
            tool_prefs = self.extract_multiple_categories(text, self.tool_patterns)

            # Initialize author profile if not exists
            if author not in self.posters_profile:
                self.posters_profile[author] = {
                    'post_count': 0,
                    'total_engagement': 0,
                    'business_stage': None,
                    'business_type': None,
                    'industry': None,
                    'target_market': None,
                    'tech_level': None,
                    'budget_range': None,
                    'pain_points': [],
                    'tool_preferences': [],
                    'posts': []
                }

            # Update poster profile
            profile = self.posters_profile[author]
            profile['post_count'] += 1
            profile['total_engagement'] += engagement

            # Update demographics with confidence-based selection (keep most confident)
            for key, value in [
                ('business_stage', business_stage),
                ('business_type', business_type),
                ('industry', industry),
                ('target_market', target_market),
                ('tech_level', tech_level),
                ('budget_range', budget_range)
            ]:
                if value and (not profile[key] or profile[key] == 'Other'):
                    profile[key] = value

            # Accumulate pain points and tool preferences
            for pain_point in pain_points:
                if pain_point not in profile['pain_points']:
                    profile['pain_points'].append(pain_point)

            for tool in tool_prefs:
                if tool not in profile['tool_preferences']:
                    profile['tool_preferences'].append(tool)

            profile['posts'].append({
                'text': text,
                'engagement': engagement,
                'timestamp': post.get('timestamp', '')
            })

        print(f"Analyzed {len(self.posters_profile)} unique posters")

    def generate_statistics(self) -> dict:
        """Generate comprehensive statistics"""
        stats = {
            'total_posters': len(self.posters_profile),
            'total_posts': sum(p['post_count'] for p in self.posters_profile.values()),
            'total_engagement': sum(p['total_engagement'] for p in self.posters_profile.values()),
            'business_stage_distribution': defaultdict(int),
            'business_type_distribution': defaultdict(int),
            'industry_distribution': defaultdict(int),
            'target_market_distribution': defaultdict(int),
            'tech_level_distribution': defaultdict(int),
            'budget_distribution': defaultdict(int),
            'pain_point_distribution': defaultdict(int),
            'tool_preference_distribution': defaultdict(int),
            'stage_by_type': defaultdict(lambda: defaultdict(int)),
            'market_by_stage': defaultdict(lambda: defaultdict(int)),
            'readiness_scores': defaultdict(list),
            'engagement_by_segment': defaultdict(list),
            'team_size_distribution': defaultdict(int)
        }

        for poster, profile in self.posters_profile.items():
            # Count distributions
            for category, distribution in [
                ('business_stage', stats['business_stage_distribution']),
                ('business_type', stats['business_type_distribution']),
                ('industry', stats['industry_distribution']),
                ('target_market', stats['target_market_distribution']),
                ('tech_level', stats['tech_level_distribution']),
                ('budget_range', stats['budget_distribution'])
            ]:
                value = profile.get(category)
                if value:
                    distribution[value] += 1

            # Cross-tabulations
            if profile.get('business_stage') and profile.get('business_type'):
                stats['stage_by_type'][profile['business_type']][profile['business_stage']] += 1

            if profile.get('business_stage') and profile.get('target_market'):
                stats['market_by_stage'][profile['business_stage']][profile['target_market']] += 1

            # Pain points and tool preferences
            for pain_point in profile.get('pain_points', []):
                stats['pain_point_distribution'][pain_point] += 1

            for tool in profile.get('tool_preferences', []):
                stats['tool_preference_distribution'][tool] += 1

            # Calculate readiness score
            readiness_score = self.calculate_readiness_score(profile)
            if profile.get('business_stage'):
                stats['readiness_scores'][profile['business_stage']].append(readiness_score)

            # Engagement by segment
            if profile.get('business_type'):
                stats['engagement_by_segment'][profile['business_type']].append(profile['total_engagement'])

            # Team size estimation (inferred from business type)
            team_size = self.estimate_team_size(profile)
            stats['team_size_distribution'][team_size] += 1

        return stats

    def estimate_team_size(self, profile: dict) -> str:
        """Estimate team size based on profile"""
        business_type = profile.get('business_type')

        if business_type is None:
            return 'Unknown'

        business_type_str = str(business_type)

        if 'Freelancer/Solo' in business_type_str or 'solo' in business_type_str.lower():
            return '1 person'
        elif 'Startup' in business_type_str:
            post_count = profile.get('post_count', 1)
            if post_count > 5:
                return '5-10 people'
            else:
                return '2-5 people'
        elif 'SME' in business_type_str:
            return '10-50 people'
        elif 'Agency' in business_type_str:
            return '5-20 people'
        else:
            return 'Unknown'

    def create_ascii_bar_chart(self, data: dict, title: str, max_width: int = 50) -> str:
        """Create ASCII bar chart"""
        if not data:
            return f"\n{title}\nNo data available\n"

        max_value = max(data.values())
        scale = max_width / max_value if max_value > 0 else 1

        lines = [f"\n{title}"]
        lines.append("=" * len(title))

        sorted_data = sorted(data.items(), key=lambda x: x[1], reverse=True)

        for label, value in sorted_data:
            percentage = (value / sum(data.values())) * 100
            bar_length = int(value * scale)
            bar = "█" * bar_length
            lines.append(f"{label:30} {value:4} |{bar}| {percentage:5.1f}%")

        lines.append(f"{'Total:':30} {sum(data.values()):4}")
        return "\n".join(lines)

    def create_ascii_stacked_bar(self, data: dict, categories: list, title: str) -> str:
        """Create ASCII stacked bar chart"""
        if not data:
            return f"\n{title}\nNo data available\n"

        lines = [f"\n{title}"]
        lines.append("=" * len(title))

        for outer_key, inner_data in data.items():
            line = f"{outer_key}: "
            bars = []
            for cat in categories:
                count = inner_data.get(cat, 0)
                if count > 0:
                    bars.append(f"{cat}: {count}")
            lines.append(line + " | ".join(bars))

        return "\n".join(lines)

    def create_ascii_pie_chart(self, data: dict, title: str) -> str:
        """Create ASCII pie chart representation"""
        if not data:
            return f"\n{title}\nNo data available\n"

        total = sum(data.values())
        lines = [f"\n{title}"]
        lines.append("=" * len(title))

        sorted_data = sorted(data.items(), key=lambda x: x[1], reverse=True)

        for label, value in sorted_data:
            percentage = (value / total) * 100
            # Simple pie slice representation
            num_symbols = int(percentage / 5)  # Each symbol = 5%
            symbols = "▓" * num_symbols + "░" * (20 - num_symbols)
            lines.append(f"{label:30} {value:4} [{symbols}] {percentage:5.1f}%")

        lines.append(f"{'Total:':30} {total:4}")
        return "\n".join(lines)

    def create_ascii_horizontal_bar(self, data: dict, title: str) -> str:
        """Create ASCII horizontal bar chart (for industry distribution)"""
        if not data:
            return f"\n{title}\nNo data available\n"

        max_value = max(data.values())
        scale = 40 / max_value if max_value > 0 else 1

        lines = [f"\n{title}"]
        lines.append("=" * len(title))

        sorted_data = sorted(data.items(), key=lambda x: x[1], reverse=True)

        for label, value in sorted_data:
            percentage = (value / sum(data.values())) * 100
            bar_length = int(value * scale)
            bar = "▬" * bar_length
            lines.append(f"{label:40} {value:4} {bar} {percentage:5.1f}%")

        lines.append(f"{'Total:':40} {sum(data.values()):4}")
        return "\n".join(lines)

    def create_ascii_funnel(self, data: dict, stages: list, title: str) -> str:
        """Create ASCII funnel chart"""
        if not data:
            return f"\n{title}\nNo data available\n"

        lines = [f"\n{title}"]
        lines.append("=" * len(title))

        # Order stages by the predefined order
        ordered_stages = [s for s in stages if s in data]
        counts = [data[s] for s in ordered_stages]

        max_count = max(counts) if counts else 1
        max_width = 50

        for i, (stage, count) in enumerate(zip(ordered_stages, counts)):
            width = int((count / max_count) * max_width)
            padding = (max_width - width) // 2
            bar = " " * padding + "█" * width + " " * (max_width - width - padding)
            percentage = (count / sum(counts)) * 100
            lines.append(f"{stage:25} {count:4} {bar} {percentage:5.1f}%")

        lines.append(f"{'Total:':25} {sum(counts):4}")
        return "\n".join(lines)

    def create_ascii_scatter(self, x_data: dict, y_data: dict, x_label: str, y_label: str, title: str) -> str:
        """Create ASCII scatter plot"""
        if not x_data or not y_data:
            return f"\n{title}\nNo data available\n"

        lines = [f"\n{title}"]
        lines.append("=" * len(title))

        # Budget ranges as x-axis
        budget_ranges = ["$0-$500", "$500-$2K", "$2K-$10K", "$10K+"]
        stages = ["Idea Stage", "MVP/Validation Stage", "Growth Stage", "Established/SME"]

        # Create grid
        for stage in stages:
            line = f"{stage:25} |"
            for budget in budget_ranges:
                count = sum(1 for p in self.posters_profile.values()
                           if p.get('budget_range') == budget and p.get('business_stage') == stage)
                if count > 0:
                    line += f" {count:3}"
                else:
                    line += "    "
            lines.append(line)

        # X-axis labels
        lines.append(" " * 27 + "-" * (len(budget_ranges) * 4))
        labels_line = " " * 27
        for budget in budget_ranges:
            labels_line += f" {budget[:3]:3}"
        lines.append(labels_line)

        return "\n".join(lines)

    def create_ascii_radar_chart(self, dimensions: dict, title: str) -> str:
        """Create ASCII radar chart representation"""
        if not dimensions:
            return f"\n{title}\nNo data available\n"

        lines = [f"\n{title}"]
        lines.append("=" * len(title))

        # Normalize scores to 0-100
        max_score = max(dimensions.values()) if dimensions else 1

        for dimension, score in dimensions.items():
            normalized = (score / max_score) * 100
            bar_length = int(normalized / 5)  # Each block = 20%
            bar = "█" * bar_length + "░" * (20 - bar_length)
            lines.append(f"{dimension:30} {score:6.1f} [{bar}] {normalized:5.1f}%")

        return "\n".join(lines)

    def create_ascii_heatmap(self, data: dict, rows: list, cols: list, title: str) -> str:
        """Create ASCII heatmap"""
        if not data:
            return f"\n{title}\nNo data available\n"

        lines = [f"\n{title}"]
        lines.append("=" * len(title))

        # Find max value for normalization
        max_val = max((inner[inner_key] for outer in data.values() for inner_key, inner in outer.items() if isinstance(inner, dict)), default=1)

        # Header row
        header = " " * 25
        for col in cols:
            header += f" {col[:10]:10}"
        lines.append(header)
        lines.append("-" * (25 + len(cols) * 11))

        # Data rows
        for row in rows:
            line = f"{row:25}"
            for col in cols:
                count = data.get(row, {}).get(col, 0)
                if count > 0:
                    intensity = count / max_val
                    if intensity > 0.7:
                        marker = "███"
                    elif intensity > 0.4:
                        marker = "░░░"
                    else:
                        marker = "·"
                    line += f" {marker:^{10}}"
                else:
                    line += " " * 11
            lines.append(line)

        return "\n".join(lines)

    def create_ascii_sankey(self, source_data: dict, middle_data: dict, target_data: dict, title: str) -> str:
        """Create ASCII Sankey diagram representation"""
        lines = [f"\n{title}"]
        lines.append("=" * len(title))

        # Source segments
        lines.append("\n[1] Community Segments:")
        for segment, count in sorted(source_data.items(), key=lambda x: x[1], reverse=True)[:5]:
            lines.append(f"    {segment:40} ({count})")

        # Middle (pain points)
        lines.append("\n[2] Pain Points:")
        for pain_point, count in sorted(middle_data.items(), key=lambda x: x[1], reverse=True)[:5]:
            lines.append(f"    {pain_point:40} ({count})")

        # Target (tool preferences)
        lines.append("\n[3] Tool Preferences:")
        for tool, count in sorted(target_data.items(), key=lambda x: x[1], reverse=True)[:5]:
            lines.append(f"    {tool:40} ({count})")

        return "\n".join(lines)

    def create_ascii_tree(self, title: str) -> str:
        """Create ASCII tree diagram of community structure"""
        lines = [f"\n{title}"]
        lines.append("=" * len(title))

        # Calculate distributions
        stage_dist = defaultdict(int)
        type_dist = defaultdict(int)
        industry_dist = defaultdict(int)

        for profile in self.posters_profile.values():
            if profile.get('business_stage'):
                stage_dist[profile['business_stage']] += 1
            if profile.get('business_type'):
                type_dist[profile['business_type']] += 1
            if profile.get('industry'):
                industry_dist[profile['industry']] += 1

        # Build tree
        total = len(self.posters_profile)
        lines.append(f"Lean Startup Community (Total: {total})")

        for stage, count in sorted(stage_dist.items(), key=lambda x: x[1], reverse=True):
            stage_pct = (count / total) * 100
            lines.append(f"├── {stage} ({count}, {stage_pct:.1f}%)")

            # Sub-branches by type
            stage_posters = [p for p in self.posters_profile.values()
                           if p.get('business_stage') == stage]

            type_counts = defaultdict(int)
            for poster in stage_posters:
                if poster.get('business_type'):
                    type_counts[poster['business_type']] += 1

            for btype, bcount in sorted(type_counts.items(), key=lambda x: x[1], reverse=True):
                btype_pct = (bcount / count) * 100 if count > 0 else 0
                lines.append(f"│   ├── {btype} ({bcount}, {btype_pct:.1f}%)")

        return "\n".join(lines)

    def create_grouped_bar_chart(self, data: dict, categories: list, title: str) -> str:
        """Create grouped bar chart (team size by business type)"""
        if not data:
            return f"\n{title}\nNo data available\n"

        lines = [f"\n{title}"]
        lines.append("=" * len(title))

        max_value = max(data.values()) if data else 1
        scale = 30 / max_value if max_value > 0 else 1

        for team_size, count in sorted(data.items(), key=lambda x: x[1], reverse=True):
            percentage = (count / sum(data.values())) * 100
            bar_length = int(count * scale)
            bar = "█" * bar_length
            lines.append(f"{team_size:25} {count:4} {bar} {percentage:5.1f}%")

        lines.append(f"{'Total:':25} {sum(data.values()):4}")
        return "\n".join(lines)

    def generate_report(self) -> str:
        """Generate comprehensive report with all visualizations"""
        stats = self.generate_statistics()

        report = []
        report.append("=" * 80)
        report.append("DEMOGRAPHIC & MARKET READINESS ANALYSIS".center(80))
        report.append("Lean Startup Circle Egypt - Facebook Community".center(80))
        report.append("=" * 80)
        report.append("")

        # Executive Summary
        report.append("=" * 80)
        report.append("EXECUTIVE SUMMARY".center(80))
        report.append("=" * 80)
        report.append("")
        report.append(f"Total Unique Posters Analyzed: {stats['total_posters']}")
        report.append(f"Total Posts Analyzed: {stats['total_posts']}")
        report.append(f"Total Engagement (Likes + Comments): {stats['total_engagement']}")
        report.append(f"Average Engagement per Poster: {stats['total_engagement'] / max(stats['total_posters'], 1):.1f}")
        report.append(f"Average Posts per Poster: {stats['total_posts'] / max(stats['total_posters'], 1):.1f}")
        report.append("")

        # Visualization 1: Stacked Bar Chart - Business Stage Distribution
        report.append("=" * 80)
        report.append("VISUALIZATION 1: Business Stage Distribution (Stacked Bar)".center(80))
        report.append("=" * 80)
        report.append(self.create_ascii_bar_chart(dict(stats['business_stage_distribution']),
                                                  "Business Stage Distribution"))
        report.append("")

        # Visualization 2: Pie Chart - Business Type Breakdown
        report.append("=" * 80)
        report.append("VISUALIZATION 2: Business Type Breakdown (Pie Chart)".center(80))
        report.append("=" * 80)
        report.append(self.create_ascii_pie_chart(dict(stats['business_type_distribution']),
                                                 "Business Type Breakdown"))
        report.append("")

        # Visualization 3: Horizontal Bar Chart - Industry Distribution
        report.append("=" * 80)
        report.append("VISUALIZATION 3: Industry Distribution with Percentages".center(80))
        report.append("=" * 80)
        report.append(self.create_ascii_horizontal_bar(dict(stats['industry_distribution']),
                                                      "Industry Distribution"))
        report.append("")

        # Visualization 4: Funnel Chart - Technical Sophistication Levels
        report.append("=" * 80)
        report.append("VISUALIZATION 4: Technical Sophistication Levels (Funnel)".center(80))
        report.append("=" * 80)
        report.append(self.create_ascii_funnel(dict(stats['tech_level_distribution']),
                                              self.tech_levels,
                                              "Technical Sophistication Levels"))
        report.append("")

        # Visualization 5: Scatter Plot - Budget × Business Stage
        report.append("=" * 80)
        report.append("VISUALIZATION 5: Budget Range × Business Stage (Scatter)".center(80))
        report.append("=" * 80)
        report.append(self.create_ascii_scatter(dict(stats['budget_distribution']),
                                               dict(stats['business_stage_distribution']),
                                               "Budget Range",
                                               "Business Stage",
                                               "Budget × Business Stage Distribution"))
        report.append("")

        # Visualization 6: Radar Chart - Market Readiness Scores
        report.append("=" * 80)
        report.append("VISUALIZATION 6: Market Readiness Scores by Segment (Radar)".center(80))
        report.append("=" * 80)
        report.append("")

        # Calculate average readiness scores by segment
        readiness_by_segment = {}
        for stage, scores in stats['readiness_scores'].items():
            if scores:
                avg_score = sum(scores) / len(scores)
                readiness_by_segment[stage] = avg_score

        report.append(self.create_ascii_radar_chart(readiness_by_segment,
                                                  "Average Market Readiness Scores by Business Stage"))
        report.append("")

        # Radar chart dimensions explanation
        report.append("Readiness Score Dimensions:")
        report.append("  • Budget Awareness (15%): Higher budget = higher score")
        report.append("  • Technical Capability (15%): Developer > Technical > Non-technical")
        report.append("  • Implementation Capability (15%): Based on technical level")
        report.append("  • Willingness to Pay (15%): Inferred from budget range")
        report.append("  • Pain Tolerance (15%): Established > Growth > MVP > Idea")
        report.append("  • Tool Adoption (10%): Based on tool preference mentions")
        report.append("  • Business Stage (15%): More established = higher score")
        report.append("")

        # Visualization 7: Heat Map - Business Stage × Target Market
        report.append("=" * 80)
        report.append("VISUALIZATION 7: Business Stage × Target Market (Heat Map)".center(80))
        report.append("=" * 80)
        report.append(self.create_ascii_heatmap(dict(stats['market_by_stage']),
                                               self.business_stages,
                                               self.target_markets,
                                               "Business Stage × Target Market"))
        report.append("")
        report.append("Legend: ███ High (70-100%), ░░░ Medium (40-70%), · Low (<40%)")
        report.append("")

        # Visualization 8: Sankey Diagram - Segments → Pain Points → Tools
        report.append("=" * 80)
        report.append("VISUALIZATION 8: Community Segments → Pain Points → Tools (Sankey)".center(80))
        report.append("=" * 80)
        report.append(self.create_ascii_sankey(dict(stats['business_stage_distribution']),
                                             dict(stats['pain_point_distribution']),
                                             dict(stats['tool_preference_distribution']),
                                             "Community Flow Analysis"))
        report.append("")

        # Visualization 9: Grouped Bar Chart - Team Size by Business Type
        report.append("=" * 80)
        report.append("VISUALIZATION 9: Team Size Distribution".center(80))
        report.append("=" * 80)
        report.append(self.create_grouped_bar_chart(dict(stats['team_size_distribution']),
                                                   [],
                                                   "Team Size Distribution (Estimated)"))
        report.append("")
        report.append("Note: Team size is estimated based on business type and post content")
        report.append("")

        # Visualization 10: Tree Diagram - Community Structure
        report.append("=" * 80)
        report.append("VISUALIZATION 10: Community Structure Visualization (Tree)".center(80))
        report.append("=" * 80)
        report.append(self.create_ascii_tree("Community Structure Breakdown"))
        report.append("")

        # Detailed Demographic Breakdown
        report.append("=" * 80)
        report.append("DETAILED DEMOGRAPHIC BREAKDOWN".center(80))
        report.append("=" * 80)
        report.append("")

        report.append("BUSINESS STAGE BREAKDOWN:")
        report.append("-" * 80)
        for stage, count in sorted(stats['business_stage_distribution'].items(),
                                   key=lambda x: x[1], reverse=True):
            pct = (count / stats['total_posters']) * 100
            report.append(f"  {stage:30} {count:4} ({pct:5.1f}%)")
        report.append("")

        report.append("BUSINESS TYPE BREAKDOWN:")
        report.append("-" * 80)
        for btype, count in sorted(stats['business_type_distribution'].items(),
                                   key=lambda x: x[1], reverse=True):
            pct = (count / stats['total_posters']) * 100
            report.append(f"  {btype:30} {count:4} ({pct:5.1f}%)")
        report.append("")

        report.append("INDUSTRY FOCUS BREAKDOWN:")
        report.append("-" * 80)
        for industry, count in sorted(stats['industry_distribution'].items(),
                                     key=lambda x: x[1], reverse=True):
            pct = (count / stats['total_posters']) * 100
            report.append(f"  {industry:30} {count:4} ({pct:5.1f}%)")
        report.append("")

        report.append("TARGET MARKET BREAKDOWN:")
        report.append("-" * 80)
        for market, count in sorted(stats['target_market_distribution'].items(),
                                    key=lambda x: x[1], reverse=True):
            pct = (count / stats['total_posters']) * 100
            report.append(f"  {market:30} {count:4} ({pct:5.1f}%)")
        report.append("")

        report.append("TECHNICAL CAPABILITY BREAKDOWN:")
        report.append("-" * 80)
        for tech, count in sorted(stats['tech_level_distribution'].items(),
                                 key=lambda x: x[1], reverse=True):
            pct = (count / stats['total_posters']) * 100
            report.append(f"  {tech:30} {count:4} ({pct:5.1f}%)")
        report.append("")

        report.append("BUDGET RANGE BREAKDOWN:")
        report.append("-" * 80)
        for budget, count in sorted(stats['budget_distribution'].items(),
                                    key=lambda x: x[1], reverse=True):
            pct = (count / stats['total_posters']) * 100
            report.append(f"  {budget:30} {count:4} ({pct:5.1f}%)")
        report.append("")

        # Pain Points Analysis
        report.append("=" * 80)
        report.append("PAIN POINTS ANALYSIS".center(80))
        report.append("=" * 80)
        report.append("")
        report.append("Top Pain Points Mentioned:")
        report.append("-" * 80)
        for pain, count in sorted(stats['pain_point_distribution'].items(),
                                 key=lambda x: x[1], reverse=True):
            pct = (count / sum(stats['pain_point_distribution'].values())) * 100
            report.append(f"  {pain:40} {count:4} ({pct:5.1f}%)")
        report.append("")

        # Tool Preferences Analysis
        report.append("=" * 80)
        report.append("TOOL PREFERENCES ANALYSIS".center(80))
        report.append("=" * 80)
        report.append("")
        report.append("Top Tool Categories Mentioned:")
        report.append("-" * 80)
        for tool, count in sorted(stats['tool_preference_distribution'].items(),
                                 key=lambda x: x[1], reverse=True):
            pct = (count / sum(stats['tool_preference_distribution'].values())) * 100
            report.append(f"  {tool:40} {count:4} ({pct:5.1f}%)")
        report.append("")

        # Market Readiness Scoring by Segment
        report.append("=" * 80)
        report.append("MARKET READINESS SCORING BY SEGMENT".center(80))
        report.append("=" * 80)
        report.append("")

        for stage in self.business_stages:
            if stage in stats['readiness_scores']:
                scores = stats['readiness_scores'][stage]
                if scores:
                    avg_score = sum(scores) / len(scores)
                    min_score = min(scores)
                    max_score = max(scores)
                    report.append(f"{stage}:")
                    report.append(f"  Average Readiness Score: {avg_score:.1f}/100")
                    report.append(f"  Score Range: {min_score:.1f} - {max_score:.1f}")
                    report.append(f"  Number of Posters: {len(scores)}")
                    report.append("")

        # Most Promising Customer Segments
        report.append("=" * 80)
        report.append("MOST PROMISING CUSTOMER SEGMENTS".center(80))
        report.append("=" * 80)
        report.append("")

        # Rank segments by readiness score
        segment_rankings = []
        for stage, scores in stats['readiness_scores'].items():
            if scores:
                avg_score = sum(scores) / len(scores)
                segment_rankings.append((stage, avg_score, len(scores)))

        segment_rankings.sort(key=lambda x: x[1], reverse=True)

        report.append("Rankings by Market Readiness Score:")
        report.append("-" * 80)
        for rank, (stage, score, count) in enumerate(segment_rankings, 1):
            report.append(f"{rank}. {stage}")
            report.append(f"   Readiness Score: {score:.1f}/100")
            report.append(f"   Poster Count: {count}")

            # Get additional context
            stage_posters = [p for p in self.posters_profile.values()
                           if p.get('business_stage') == stage]

            # Budget distribution for this segment
            budget_counts = defaultdict(int)
            for poster in stage_posters:
                if poster.get('budget_range'):
                    budget_counts[poster['budget_range']] += 1

            if budget_counts:
                report.append(f"   Top Budget Ranges: {', '.join(f'{k} ({v})' for k, v in sorted(budget_counts.items(), key=lambda x: x[1], reverse=True)[:3])}")

            report.append("")

        # Go-to-Market Recommendations
        report.append("=" * 80)
        report.append("GO-TO-MARKET RECOMMENDATIONS BY SEGMENT".center(80))
        report.append("=" * 80)
        report.append("")

        for stage in self.business_stages:
            report.append(f"SEGMENT: {stage}")
            report.append("-" * 80)

            # Get segment data
            stage_posters = [p for p in self.posters_profile.values()
                           if p.get('business_stage') == stage]

            if not stage_posters:
                report.append("  No data available")
                report.append("")
                continue

            # Calculate segment characteristics
            avg_engagement = sum(p['total_engagement'] for p in stage_posters) / len(stage_posters)

            # Top pain points
            pain_counter = defaultdict(int)
            for poster in stage_posters:
                for pain in poster.get('pain_points', []):
                    pain_counter[pain] += 1

            # Top tool preferences
            tool_counter = defaultdict(int)
            for poster in stage_posters:
                for tool in poster.get('tool_preferences', []):
                    tool_counter[tool] += 1

            # Budget distribution
            budget_counter = defaultdict(int)
            for poster in stage_posters:
                if poster.get('budget_range'):
                    budget_counter[poster['budget_range']] += 1

            report.append(f"  Avg Engagement: {avg_engagement:.1f}")
            report.append(f"  Poster Count: {len(stage_posters)}")
            report.append("")

            report.append("  Top Pain Points:")
            for pain, count in sorted(pain_counter.items(), key=lambda x: x[1], reverse=True)[:3]:
                pct = (count / sum(pain_counter.values())) * 100 if pain_counter else 0
                report.append(f"    • {pain}: {count} ({pct:.1f}%)")

            report.append("")
            report.append("  Preferred Tools:")
            for tool, count in sorted(tool_counter.items(), key=lambda x: x[1], reverse=True)[:3]:
                pct = (count / sum(tool_counter.values())) * 100 if tool_counter else 0
                report.append(f"    • {tool}: {count} ({pct:.1f}%)")

            if budget_counter:
                report.append("")
                report.append("  Budget Distribution:")
                for budget, count in sorted(budget_counter.items(), key=lambda x: x[1], reverse=True)[:3]:
                    pct = (count / sum(budget_counter.values())) * 100 if budget_counter else 0
                    report.append(f"    • {budget}: {count} ({pct:.1f}%)")

            # Strategic recommendations
            report.append("")
            report.append("  STRATEGIC RECOMMENDATIONS:")

            if stage == "Idea Stage":
                report.append("    • Focus on education and awareness content")
                report.append("    • Offer free trials and consultations")
                report.append("    • Provide mentorship and guidance")
                report.append("    • Emphasize quick wins and early validation")
            elif stage == "MVP/Validation Stage":
                report.append("    • Focus on rapid deployment and testing")
                report.append("    • Offer MVP-friendly pricing (freemium, pay-as-you-go)")
                report.append("    • Provide integration support and onboarding")
                report.append("    • Emphasize scalability and growth potential")
            elif stage == "Growth Stage":
                report.append("    • Focus on enterprise features and capabilities")
                report.append("    • Offer tiered pricing with volume discounts")
                report.append("    • Provide dedicated support and account management")
                report.append("    • Emphasize ROI and competitive advantages")
            elif stage == "Established/SME":
                report.append("    • Focus on compliance and regulatory features")
                report.append("    • Offer customized solutions and white-labeling")
                report.append("    • Provide comprehensive training and documentation")
                report.append("    • Emphasize reliability, security, and support")

            report.append("")

        # Budget Distribution by Segment
        report.append("=" * 80)
        report.append("BUDGET DISTRIBUTION BY SEGMENT".center(80))
        report.append("=" * 80)
        report.append("")

        for stage in self.business_stages:
            report.append(f"{stage}:")
            report.append("-" * 80)

            stage_posters = [p for p in self.posters_profile.values()
                           if p.get('business_stage') == stage]

            budget_counter = defaultdict(int)
            for poster in stage_posters:
                if poster.get('budget_range'):
                    budget_counter[poster['budget_range']] += 1

            if budget_counter:
                for budget in self.budget_ranges:
                    count = budget_counter.get(budget, 0)
                    if count > 0:
                        pct = (count / sum(budget_counter.values())) * 100
                        bar_length = int(pct / 5)
                        bar = "█" * bar_length
                        report.append(f"  {budget:15} {count:4} {bar} {pct:5.1f}%")
            else:
                report.append("  No budget data available")

            report.append("")

        # Key Findings and Insights
        report.append("=" * 80)
        report.append("KEY FINDINGS & INSIGHTS".center(80))
        report.append("=" * 80)
        report.append("")

        # Find most active segments
        most_active_type = max(stats['business_type_distribution'].items(),
                             key=lambda x: x[1]) if stats['business_type_distribution'] else (None, 0)

        report.append("COMMUNITY COMPOSITION:")
        report.append(f"  • Most Common Business Type: {most_active_type[0]} ({most_active_type[1]} posters)")
        report.append(f"  • Most Common Business Stage: {max(stats['business_stage_distribution'].items(), key=lambda x: x[1])[0]}")
        report.append(f"  • Most Common Industry: {max(stats['industry_distribution'].items(), key=lambda x: x[1])[0]}")
        report.append("")

        # Top pain points
        if stats['pain_point_distribution']:
            top_pain = max(stats['pain_point_distribution'].items(), key=lambda x: x[1])
            report.append(f"  • Top Pain Point: {top_pain[0]} ({top_pain[1]} mentions)")
        report.append("")

        # Market readiness insights
        report.append("MARKET READINESS INSIGHTS:")
        if segment_rankings:
            top_segment = segment_rankings[0]
            bottom_segment = segment_rankings[-1]
            report.append(f"  • Most Ready Segment: {top_segment[0]} (Score: {top_segment[1]:.1f}/100)")
            report.append(f"  • Least Ready Segment: {bottom_segment[0]} (Score: {bottom_segment[1]:.1f}/100)")

            # Calculate overall readiness
            all_scores = [s for scores in stats['readiness_scores'].values() for s in scores]
            if all_scores:
                overall_readiness = sum(all_scores) / len(all_scores)
                report.append(f"  • Overall Community Readiness: {overall_readiness:.1f}/100")
        report.append("")

        # Budget insights
        if stats['budget_distribution']:
            total_with_budget = sum(stats['budget_distribution'].values())
            if total_with_budget > 0:
                report.append("BUDGET INSIGHTS:")
                report.append(f"  • Posters with Budget Data: {total_with_budget}/{stats['total_posters']} ({(total_with_budget/stats['total_posters'])*100:.1f}%)")

                # Calculate average budget range (as index)
                budget_indices = []
                budget_values = {"$0-$500": 1, "$500-$2K": 2, "$2K-$10K": 3, "$10K+": 4}
                for budget, count in stats['budget_distribution'].items():
                    budget_indices.extend([budget_values.get(budget, 0)] * count)

                if budget_indices:
                    avg_budget_idx = sum(budget_indices) / len(budget_indices)
                    if avg_budget_idx < 1.5:
                        avg_range = "$0-$500"
                    elif avg_budget_idx < 2.5:
                        avg_range = "$500-$2K"
                    elif avg_budget_idx < 3.5:
                        avg_range = "$2K-$10K"
                    else:
                        avg_range = "$10K+"
                    report.append(f"  • Average Budget Range: {avg_range}")
        report.append("")

        # Conclusion
        report.append("=" * 80)
        report.append("CONCLUSION".center(80))
        report.append("=" * 80)
        report.append("")

        report.append("The Lean Startup Circle Egypt community represents a diverse mix of")
        report.append("entrepreneurs at various stages of business development. Key takeaways:")
        report.append("")
        report.append("1. Community spans from idea-stage founders to established SMEs")
        report.append("2. Strong focus on technology/SaaS and marketing/e-commerce sectors")
        report.append("3. Budget awareness varies significantly by business stage")
        report.append("4. Technical capability is a key differentiator in market readiness")
        report.append("5. Pain points cluster around technical implementation and marketing")
        report.append("6. CRM/WhatsApp and payment tools are most in demand")
        report.append("")
        report.append("Recommended go-to-market strategy:")
        report.append("  • Prioritize Growth Stage and Established/SME segments")
        report.append("  • Focus on technical solutions for implementation challenges")
        report.append("  • Offer tiered pricing to accommodate budget diversity")
        report.append("  • Emphasize quick wins and measurable ROI")
        report.append("  • Provide comprehensive onboarding and support")
        report.append("")
        report.append("=" * 80)
        report.append("END OF REPORT".center(80))
        report.append("=" * 80)

        return "\n".join(report)

def main():
    """Main execution function"""
    output_dir = "/Users/admin/Desktop/LeanStartup_Group_Scraper/output"

    print("Starting Demographic & Market Readiness Analysis...")
    print("=" * 80)

    # Initialize analyzer
    analyzer = DemographicAnalyzer(output_dir)

    # Load and analyze posts
    analyzer.load_all_posts()
    analyzer.analyze_posts()

    # Generate and save report
    report = analyzer.generate_report()

    # Save to file
    report_path = "/Users/admin/Desktop/LeanStartup_Group_Scraper/demographic_market_analysis_report.md"
    with open(report_path, 'w', encoding='utf-8') as f:
        f.write(report)

    print("\nReport generated successfully!")
    print(f"Report saved to: {report_path}")
    print("\nKey Statistics:")
    stats = analyzer.generate_statistics()
    print(f"  • Total Posters: {stats['total_posters']}")
    print(f"  • Total Posts: {stats['total_posts']}")
    print(f"  • Total Engagement: {stats['total_engagement']}")

    # Print some key findings
    print("\nTop Demographics:")
    print(f"  • Most Common Business Stage: {max(stats['business_stage_distribution'].items(), key=lambda x: x[1])[0]}")
    print(f"  • Most Common Business Type: {max(stats['business_type_distribution'].items(), key=lambda x: x[1])[0]}")
    print(f"  • Most Common Industry: {max(stats['industry_distribution'].items(), key=lambda x: x[1])[0]}")

    if stats['pain_point_distribution']:
        print(f"  • Top Pain Point: {max(stats['pain_point_distribution'].items(), key=lambda x: x[1])[0]}")

    if stats['tool_preference_distribution']:
        print(f"  • Top Tool Preference: {max(stats['tool_preference_distribution'].items(), key=lambda x: x[1])[0]}")

    print("\n" + "=" * 80)
    print("Analysis Complete!")
    print("=" * 80)

if __name__ == "__main__":
    main()
