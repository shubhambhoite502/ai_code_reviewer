def format_review(sections: dict) -> str:
    parts = []
    title = sections.get("title", "🤖 AI Code Review")
    parts.append(f"### {title}\n")
    if "effort_estimate" in sections:
        parts.append(f"**Effort Estimate**\n{sections['effort_estimate']}\n")
    if "flags" in sections:
        parts.append(f"**Flags**\n{', '.join(sections['flags'])}\n")
    if "summary" in sections:
        parts.append(f"**Summary**\n{sections['summary']}\n")
    if "issues" in sections and sections["issues"]:
        parts.append("**Issues Found**")
        for i, issue in enumerate(sections["issues"], 1):
            parts.append(f"{i}. {issue}")
        parts.append("")
    if "suggestions" in sections and sections["suggestions"]:
        parts.append("**Suggestions**")
        for i, sug in enumerate(sections["suggestions"], 1):
            parts.append(f"{i}. {sug}")
        parts.append("")
    if "security" in sections and sections["security"]:
        parts.append("**Security Notes**")
        for i, sec in enumerate(sections["security"], 1):
            parts.append(f"{i}. {sec}")
        parts.append("")
    if "must_do" in sections and sections["must_do"]:
        parts.append("**Must Do**")
        for i, must in enumerate(sections["must_do"], 1):
            parts.append(f"{i}. {must}")
        parts.append("")
    if "good_to_have" in sections and sections["good_to_have"]:
        parts.append("**Good To Have**")
        for i, good in enumerate(sections["good_to_have"], 1):
            parts.append(f"{i}. {good}")
        parts.append("")
    if "final_thoughts" in sections:
        parts.append(f"**Final Thoughts**\n{sections['final_thoughts']}\n")
    return "\n".join(parts)
