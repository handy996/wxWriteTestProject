package com.example.editorial.bootstrap;

import com.example.editorial.article.job.*;
import com.example.editorial.article.version.*;
import com.example.editorial.article.proposal.*;
import com.example.editorial.audit.AuditSink;
import com.example.editorial.shared.*;
import com.fasterxml.jackson.databind.JsonNode;
import java.util.*;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.boot.autoconfigure.condition.*;
import org.springframework.context.annotation.*;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.transaction.PlatformTransactionManager;

/** Proposed composition root only, requires reviewed T06 extension patch. */
@Configuration(proxyBeanMethods=false)
@ConditionalOnProperty(name="editorial.version.enabled",havingValue="true")
public class VersionIntegration {
    @Bean PageCursor versionCursor(@Value("${editorial.identity.cursor-key}") String key){return new PageCursor(key);}
    @Bean @ConditionalOnMissingBean VersionPorts.HumanFence versionFence(){return VersionPorts.unavailableFence();}
    @Bean @ConditionalOnMissingBean VersionPorts.Executions versionExecutions(){return VersionPorts.unavailableExecutions();}
    @Bean @ConditionalOnMissingBean VersionPorts.References versionReferences(){return VersionPorts.unavailableReferences();}
    @Bean VersionPorts.Audit versionAudit(AuditSink audit){return (a,action,j,id,b,n)->audit.append(a,new AuditSink.Event(action,j,"VERSION",id,b,n)).id();}
    @Bean VersionPorts.Store versionStore(ArticleService articles,com.example.editorial.storage.StorageBackend backend){return new VersionPorts.Store(){
        private void localOnly(){if(!(backend instanceof com.example.editorial.storage.LocalStorageBackend))throw new PublicFailure(503,"STORAGE_COMMIT_NOT_READY");}
        public ArticleService.PreparedVersion prepare(ActorContext a,UUID j,VersionPorts.Draft d,com.example.editorial.article.ast.ArticleAst.References refs){localOnly();return articles.prepareVersionExtended(a,j,d.base(),d.etag(),d.kind(),d.source(),d.title(),d.subtitle(),d.ast(),d.summary(),d.mappings(),d.execution(),d.inputHash(),refs,d.restoredFrom(),d.retained());}
        public UUID append(ActorContext a,ArticleService.PreparedVersion p,boolean retained,JsonNode style){localOnly();return articles.appendVersionExtended(a,p,retained,style);}
        public List<JsonNode> page(ActorContext a,UUID j,long before,int limit){return articles.versionPage(a,j,before,limit);}
    };}
    @Bean VersionService versionService(ArticleService a,VersionPorts.Store s,VersionPorts.References r,VersionPorts.HumanFence f,VersionPorts.Executions e,PageCursor c,PlatformTransactionManager m,ProposalService proposals){return new VersionService(a,s,r,f,e,c,m,proposals::staleOther);}
    @Bean ProposalService proposalService(JdbcTemplate db,ArticleService a,VersionPorts.Audit audit,PageCursor c){return new ProposalService(db,a,audit,c);}
}
