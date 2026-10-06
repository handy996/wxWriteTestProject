package com.example.editorial.editorial.skill;

import java.util.List;

/** The four frozen editorial prompt roles. A SkillConfig must bind all four (each a distinct agentName). */
public final class BaselineAgents {
    public static final String ANALYZER = "Analyzer";
    public static final String WRITER = "Writer";
    public static final String REVIEWER = "EditorialReviewer";
    public static final String REVISION = "WriterRevision";
    public static final List<String> ALL = List.of(ANALYZER, WRITER, REVIEWER, REVISION);
    private BaselineAgents() {}
}
