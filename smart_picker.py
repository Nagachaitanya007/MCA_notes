import json
import os
import random
import sys

def pick_daily_topic(category_filter=None):
    base_dir = os.path.dirname(os.path.abspath(__file__))
    syllabus_file = os.path.join(base_dir, "syllabus.json")
    tracker_file = os.path.join(base_dir, ".github", "covered_topics.json")

    # 1. Load Syllabus
    with open(syllabus_file, "r", encoding="utf-8") as f:
        syllabus = json.load(f)

    # 2. Load Progress
    covered = {}
    if os.path.exists(tracker_file):
        with open(tracker_file, "r", encoding="utf-8") as f:
            covered = json.load(f)

    # 3. Find candidates
    candidates = []
    for category, topics in syllabus.items():
        # Apply filter if provided (e.g. "Java" in "Java & Core")
        if category_filter and category_filter.lower() not in category.lower():
            continue
            
        for topic in topics:
            count = len(covered.get(topic, []))
            candidates.append({
                "category": category,
                "topic": topic,
                "count": count
            })

    if not candidates:
        print(f"No topics found for filter: {category_filter}")
        sys.exit(1)

    # Sort by count (fewest first) and pick from the bottom tier
    candidates.sort(key=lambda x: x["count"])
    min_count = candidates[0]["count"]
    fresh_candidates = [c for c in candidates if c["count"] == min_count]

    # Pick a random one from the least-covered topics
    chosen = random.choice(fresh_candidates)
    return chosen["topic"]

if __name__ == "__main__":
    filter_arg = sys.argv[1] if len(sys.argv) > 1 else None
    print(pick_daily_topic(filter_arg))
