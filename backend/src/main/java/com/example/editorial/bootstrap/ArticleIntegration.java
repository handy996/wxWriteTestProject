package com.example.editorial.bootstrap;

import com.example.editorial.article.ast.ArticleAst;
import com.example.editorial.article.job.*;
import com.example.editorial.audit.AuditSink;
import com.example.editorial.editorial.skill.*;
import com.example.editorial.settings.policy.*;
import com.example.editorial.shared.*;
import com.example.editorial.storage.*;
import com.fasterxml.jackson.databind.JsonNode;
import java.util.UUID;
import org.springframework.beans.factory.ObjectProvider;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.boot.autoconfigure.condition.ConditionalOnMissingBean;
import org.springframework.boot.autoconfigure.condition.ConditionalOnProperty;
import org.springframework.context.annotation.*;
import org.springframework.jdbc.core.JdbcTemplate;

/** Proposed main-agent composition-root file. Not installed in the shared application by T06. */
@Configuration(proxyBeanMethods=false)
@ConditionalOnProperty(name="editorial.article.enabled",havingValue="true")
public class ArticleIntegration {
    @Bean @ConditionalOnMissingBean ArticlePorts.Changes articleChanges() { return ArticlePorts.unavailableChanges(); }
    @Bean @ConditionalOnMissingBean ArticlePorts.Evidence articleEvidence() { return ArticlePorts.unavailableEvidence(); }
    @Bean @ConditionalOnMissingBean ArticlePorts.Deletion articleDeletion() { return ArticlePorts.unavailableDeletion(); }
    @Bean ArticleService articleService(JdbcTemplate db, SkillSnapshotPort skills, PromptService prompts, PolicyService policies,
            AuditSink audit, ObjectProvider<ObjectStore> store, ArticlePorts.Changes changes,
            ArticlePorts.Evidence evidence, JsonSchema schema, @Value("${editorial.identity.cursor-key}") String key) {
        ArticlePorts.Snapshots snapshots=(actor,id)-> {
            var skill=skills.read(actor,id);
            if(skill.status()!=PublicationStatus.PUBLISHED) throw new PublicFailure(409,"SKILL_NOT_PUBLISHED");
            var out=ArticleAst.JSON.createObjectNode();
            out.set("skill",ArticleAst.JSON.valueToTree(skill)); var ps=out.putArray("prompts");
            for(var binding:skill.config().path("promptBindings")) {
                var p=prompts.getById(UUID.fromString(binding.path("promptVersionId").asText()));
                if(p.status()!=PublicationStatus.PUBLISHED || !p.hash().equals(binding.path("hash").asText())) throw new PublicFailure(409,"PROMPT_SNAPSHOT_MISMATCH");
                var n=ArticleAst.JSON.createObjectNode().put("id",p.id().toString()).put("version",p.version()).put("hash",p.hash())
                    .put("systemTemplate",p.systemTemplate()).put("userTemplate",p.userTemplate()); n.set("outputSchema",p.outputSchema()); ps.add(n);
            }
            var policyContents=out.putArray("policies");
            for(var ref:skill.policySnapshots()) {
                var p=policies.getById(ref.id());
                if(p.status()==PublicationStatus.DRAFT || !ArticleAst.hash(p.rules()).equals(ref.hash())) throw new PublicFailure(409,"POLICY_SNAPSHOT_MISMATCH");
                var n=ArticleAst.JSON.createObjectNode().put("id",p.id().toString()).put("type",p.type().name()).put("version",p.version()).put("hash",p.hash());
                n.set("rules",p.rules());policyContents.add(n);
            }
            return out;
        };
        ArticlePorts.Objects objects=new ArticlePorts.Objects() {
            public JsonNode stage(ActorContext a,byte[] bytes) {return ArticleAst.JSON.valueToTree(store.getObject().stage(a,bytes,CanonicalRequest.digest(bytes),bytes.length));}
            public void commit(ActorContext a,JsonNode n,Ownership.ArtifactRef ref) {
                store.getObject().commitReference(a,new ObjectRef(n.path("key").asText(),n.path("hash").asText(),n.path("size").asLong(),n.path("mime").asText(),n.path("encrypted").asBoolean()),ref);
            }
        };
        return new ArticleService(db,snapshots,objects,(a,action,article,entity,before,after)->audit.append(a,new AuditSink.Event(action,article,"ARTICLE",entity,before,after)),evidence,changes,
            (body,definition)->schema.validate(body,definition),key);
    }
    @Bean ObjectRefRegistry articleObjectRegistry(ArticleService service) {
        return new ObjectRefRegistry() {
            public Resolution resolve(String key) {var owner=service.objectOwner(key);return owner==null?null:new Resolution(owner.article(),"ARTICLE_VERSION",owner.revoked());}
            public boolean referenced(String key) {return service.objectOwner(key)!=null;}
        };
    }
}
