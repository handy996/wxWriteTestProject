package com.example.editorial.editorial.skill;
import java.nio.file.*;
import org.junit.jupiter.api.Test;
import com.example.editorial.settings.policy.JsonIO;
class ReviewExportSamplesTest {
    @Test void exportExactFixedOutputsForIndependentStandardValidator() throws Exception {
        var sample=PromptContractTest.class.getDeclaredMethod("sample", String.class);
        sample.setAccessible(true);
        var data=JsonIO.MAPPER.createObjectNode();
        for(String type:java.util.List.of("AnalysisOutput","WriterOutput","ReviewOutput","RevisionOutput"))
            data.set(type,(com.fasterxml.jackson.databind.JsonNode)sample.invoke(null,type));
        Path output=Path.of("target/review-model-samples.json");
        Files.createDirectories(output.getParent());
        Files.writeString(output,JsonIO.MAPPER.writeValueAsString(data));
    }
}
