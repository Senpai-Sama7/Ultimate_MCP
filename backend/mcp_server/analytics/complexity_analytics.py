"""Advanced analytics for code complexity trends."""

from __future__ import annotations

import asyncio
from datetime import datetime, timedelta
from typing import Any, Optional

from pydantic import BaseModel

from ..database.neo4j_client import Neo4jClient


class ComplexityMetrics(BaseModel):
    """Code complexity metrics."""
    avg_complexity: float
    max_complexity: float
    min_complexity: float
    total_functions: int
    high_complexity_count: int  # Functions with complexity > 10
    complexity_distribution: dict[str, int]  # Ranges: 0-2, 3-5, 6-10, 11+


class ComplexityTrend(BaseModel):
    """Complexity trend over time."""
    date: str
    metrics: ComplexityMetrics


class LanguageComplexity(BaseModel):
    """Complexity metrics by language."""
    language: str
    metrics: ComplexityMetrics
    sample_size: int


class ComplexityAnalytics:
    """Advanced code complexity analytics engine."""
    
    def __init__(self, neo4j_client: Neo4jClient):
        self.neo4j_client = neo4j_client
    
    async def get_complexity_trends(
        self,
        days: int = 30,
        user_id: Optional[str] = None
    ) -> list[ComplexityTrend]:
        """Get complexity trends over time."""
        user_filter = "AND l.user_id = $user_id" if user_id else ""
        
        query = f"""
        MATCH (l:LintResult)
        WHERE l.timestamp >= datetime() - duration({{days: $days}})
        {user_filter}
        WITH l, date(l.timestamp) as day
        RETURN 
            day,
            avg(l.complexity) as avg_complexity,
            max(l.complexity) as max_complexity,
            min(l.complexity) as min_complexity,
            count(l) as total_functions,
            sum(CASE WHEN l.complexity > 10 THEN 1 ELSE 0 END) as high_complexity_count,
            sum(CASE WHEN l.complexity <= 2 THEN 1 ELSE 0 END) as simple_count,
            sum(CASE WHEN l.complexity > 2 AND l.complexity <= 5 THEN 1 ELSE 0 END) as moderate_count,
            sum(CASE WHEN l.complexity > 5 AND l.complexity <= 10 THEN 1 ELSE 0 END) as complex_count,
            sum(CASE WHEN l.complexity > 10 THEN 1 ELSE 0 END) as very_complex_count
        ORDER BY day
        """
        
        params = {"days": days}
        if user_id:
            params["user_id"] = user_id
        
        results = await self.neo4j_client.execute_read(query, params)
        
        trends = []
        for row in results:
            metrics = ComplexityMetrics(
                avg_complexity=float(row["avg_complexity"] or 0),
                max_complexity=float(row["max_complexity"] or 0),
                min_complexity=float(row["min_complexity"] or 0),
                total_functions=int(row["total_functions"] or 0),
                high_complexity_count=int(row["high_complexity_count"] or 0),
                complexity_distribution={
                    "0-2": int(row["simple_count"] or 0),
                    "3-5": int(row["moderate_count"] or 0),
                    "6-10": int(row["complex_count"] or 0),
                    "11+": int(row["very_complex_count"] or 0),
                }
            )
            
            trends.append(ComplexityTrend(
                date=row["day"].isoformat(),
                metrics=metrics
            ))
        
        return trends
    
    async def get_language_complexity_comparison(
        self,
        days: int = 30
    ) -> list[LanguageComplexity]:
        """Compare complexity metrics across languages."""
        query = """
        MATCH (l:LintResult)
        WHERE l.timestamp >= datetime() - duration({days: $days})
        AND l.language IS NOT NULL
        WITH l.language as language, l.complexity as complexity
        RETURN 
            language,
            avg(complexity) as avg_complexity,
            max(complexity) as max_complexity,
            min(complexity) as min_complexity,
            count(*) as sample_size,
            sum(CASE WHEN complexity > 10 THEN 1 ELSE 0 END) as high_complexity_count,
            sum(CASE WHEN complexity <= 2 THEN 1 ELSE 0 END) as simple_count,
            sum(CASE WHEN complexity > 2 AND complexity <= 5 THEN 1 ELSE 0 END) as moderate_count,
            sum(CASE WHEN complexity > 5 AND complexity <= 10 THEN 1 ELSE 0 END) as complex_count,
            sum(CASE WHEN complexity > 10 THEN 1 ELSE 0 END) as very_complex_count
        ORDER BY avg_complexity DESC
        """
        
        results = await self.neo4j_client.execute_read(query, {"days": days})
        
        language_metrics = []
        for row in results:
            metrics = ComplexityMetrics(
                avg_complexity=float(row["avg_complexity"] or 0),
                max_complexity=float(row["max_complexity"] or 0),
                min_complexity=float(row["min_complexity"] or 0),
                total_functions=int(row["sample_size"] or 0),
                high_complexity_count=int(row["high_complexity_count"] or 0),
                complexity_distribution={
                    "0-2": int(row["simple_count"] or 0),
                    "3-5": int(row["moderate_count"] or 0),
                    "6-10": int(row["complex_count"] or 0),
                    "11+": int(row["very_complex_count"] or 0),
                }
            )
            
            language_metrics.append(LanguageComplexity(
                language=row["language"],
                metrics=metrics,
                sample_size=int(row["sample_size"] or 0)
            ))
        
        return language_metrics
    
    async def get_complexity_hotspots(
        self,
        limit: int = 10,
        min_complexity: float = 10.0
    ) -> list[dict[str, Any]]:
        """Find code with highest complexity (hotspots for refactoring)."""
        query = """
        MATCH (l:LintResult)
        WHERE l.complexity >= $min_complexity
        RETURN 
            l.code_hash as code_hash,
            l.complexity as complexity,
            l.functions as functions,
            l.classes as classes,
            l.language as language,
            l.timestamp as timestamp,
            l.linter_output as issues
        ORDER BY l.complexity DESC
        LIMIT $limit
        """
        
        results = await self.neo4j_client.execute_read(query, {
            "min_complexity": min_complexity,
            "limit": limit
        })
        
        hotspots = []
        for row in results:
            hotspots.append({
                "code_hash": row["code_hash"],
                "complexity": float(row["complexity"]),
                "functions": row["functions"] or [],
                "classes": row["classes"] or [],
                "language": row["language"],
                "timestamp": row["timestamp"].isoformat() if row["timestamp"] else None,
                "issues": row["issues"] or "",
                "refactor_priority": "HIGH" if row["complexity"] > 20 else "MEDIUM"
            })
        
        return hotspots
    
    async def get_user_complexity_stats(
        self,
        user_id: str,
        days: int = 30
    ) -> dict[str, Any]:
        """Get complexity statistics for a specific user."""
        query = """
        MATCH (l:LintResult)
        WHERE l.user_id = $user_id
        AND l.timestamp >= datetime() - duration({days: $days})
        RETURN 
            avg(l.complexity) as avg_complexity,
            max(l.complexity) as max_complexity,
            min(l.complexity) as min_complexity,
            count(l) as total_submissions,
            sum(CASE WHEN l.complexity > 10 THEN 1 ELSE 0 END) as high_complexity_count,
            sum(CASE WHEN l.linter_exit_code = 0 THEN 1 ELSE 0 END) as clean_code_count,
            collect(DISTINCT l.language) as languages_used
        """
        
        results = await self.neo4j_client.execute_read(query, {
            "user_id": user_id,
            "days": days
        })
        
        if not results:
            return {
                "user_id": user_id,
                "period_days": days,
                "no_data": True
            }
        
        row = results[0]
        total_submissions = int(row["total_submissions"] or 0)
        
        return {
            "user_id": user_id,
            "period_days": days,
            "avg_complexity": float(row["avg_complexity"] or 0),
            "max_complexity": float(row["max_complexity"] or 0),
            "min_complexity": float(row["min_complexity"] or 0),
            "total_submissions": total_submissions,
            "high_complexity_rate": (
                int(row["high_complexity_count"] or 0) / total_submissions * 100
                if total_submissions > 0 else 0
            ),
            "clean_code_rate": (
                int(row["clean_code_count"] or 0) / total_submissions * 100
                if total_submissions > 0 else 0
            ),
            "languages_used": row["languages_used"] or [],
            "complexity_grade": self._calculate_complexity_grade(
                float(row["avg_complexity"] or 0)
            )
        }
    
    async def generate_complexity_report(
        self,
        days: int = 30
    ) -> dict[str, Any]:
        """Generate comprehensive complexity report."""
        # Run analytics in parallel
        trends_task = asyncio.create_task(
            self.get_complexity_trends(days)
        )
        languages_task = asyncio.create_task(
            self.get_language_complexity_comparison(days)
        )
        hotspots_task = asyncio.create_task(
            self.get_complexity_hotspots()
        )
        
        trends, languages, hotspots = await asyncio.gather(
            trends_task, languages_task, hotspots_task
        )
        
        # Calculate summary statistics
        if trends:
            latest_metrics = trends[-1].metrics
            avg_trend = sum(t.metrics.avg_complexity for t in trends) / len(trends)
        else:
            latest_metrics = ComplexityMetrics(
                avg_complexity=0, max_complexity=0, min_complexity=0,
                total_functions=0, high_complexity_count=0,
                complexity_distribution={}
            )
            avg_trend = 0
        
        return {
            "report_date": datetime.now().isoformat(),
            "period_days": days,
            "summary": {
                "current_avg_complexity": latest_metrics.avg_complexity,
                "trend_avg_complexity": avg_trend,
                "total_hotspots": len(hotspots),
                "languages_analyzed": len(languages),
            },
            "trends": [t.dict() for t in trends],
            "language_comparison": [l.dict() for l in languages],
            "complexity_hotspots": hotspots,
            "recommendations": self._generate_recommendations(
                latest_metrics, hotspots, languages
            )
        }
    
    def _calculate_complexity_grade(self, avg_complexity: float) -> str:
        """Calculate complexity grade based on average complexity."""
        if avg_complexity <= 2:
            return "A"  # Excellent
        elif avg_complexity <= 5:
            return "B"  # Good
        elif avg_complexity <= 10:
            return "C"  # Acceptable
        elif avg_complexity <= 15:
            return "D"  # Needs improvement
        else:
            return "F"  # Poor
    
    def _generate_recommendations(
        self,
        current_metrics: ComplexityMetrics,
        hotspots: list[dict],
        languages: list[LanguageComplexity]
    ) -> list[str]:
        """Generate actionable recommendations."""
        recommendations = []
        
        if current_metrics.avg_complexity > 10:
            recommendations.append(
                "Consider refactoring: Average complexity is high (>10). "
                "Break down complex functions into smaller, focused functions."
            )
        
        if current_metrics.high_complexity_count > 0:
            recommendations.append(
                f"Refactor {current_metrics.high_complexity_count} high-complexity functions. "
                "Use design patterns like Strategy or Command to reduce complexity."
            )
        
        if len(hotspots) > 5:
            recommendations.append(
                "Multiple complexity hotspots detected. Prioritize refactoring "
                "the most complex functions first."
            )
        
        # Language-specific recommendations
        for lang in languages:
            if lang.metrics.avg_complexity > 15:
                recommendations.append(
                    f"{lang.language}: Very high complexity detected. "
                    "Consider using language-specific patterns to simplify code."
                )
        
        if not recommendations:
            recommendations.append(
                "Code complexity is within acceptable ranges. "
                "Continue following good coding practices."
            )
        
        return recommendations


__all__ = ["ComplexityAnalytics", "ComplexityMetrics", "ComplexityTrend", "LanguageComplexity"]
