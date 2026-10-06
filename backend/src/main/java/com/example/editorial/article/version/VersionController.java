package com.example.editorial.article.version;

import static com.example.editorial.article.ast.ArticleAst.*;
import com.example.editorial.article.job.ArticleService;
import com.example.editorial.article.proposal.ProposalService;
import com.example.editorial.shared.*;
import com.fasterxml.jackson.databind.JsonNode;
import jakarta.servlet.http.*;
import java.util.*;
import org.springframework.boot.autoconfigure.condition.ConditionalOnProperty;
import org.springframework.web.bind.annotation.*;

@RestController
@RequestMapping("/api/v1")
@ConditionalOnProperty(name="editorial.version.enabled",havingValue="true")
public final class VersionController {
    private final ArticleService articles;private final VersionService versions;private final ProposalService proposals;private final Idempotency idem;
    public VersionController(ArticleService a,VersionService v,ProposalService p,Idempotency i){articles=a;versions=v;proposals=p;idem=i;}
    @GetMapping("/articles/{id}/versions") public JsonNode list(@PathVariable UUID id,@RequestParam(required=false) String cursor,@RequestParam(defaultValue="20") int limit){return versions.list(ActorContext.current(),id,cursor,limit);}
    @GetMapping("/articles/{id}/versions/{versionId}") public void get(@PathVariable UUID id,@PathVariable UUID versionId,HttpServletResponse res)throws Exception {var a=ActorContext.current();reply(res,response(200,a,id,articles.readVersion(a,id,versionId)));}
    @GetMapping("/articles/{id}/diff") public JsonNode diff(@PathVariable UUID id,@RequestParam UUID from,@RequestParam UUID to){return versions.diff(ActorContext.current(),id,from,to);}
    @GetMapping("/articles/{id}/diff/pages") public JsonNode diffPage(@PathVariable UUID id,@RequestParam UUID from,@RequestParam UUID to,
            @RequestParam(required=false) String cursor,@RequestParam(defaultValue="100") int limit){return versions.diffPage(ActorContext.current(),id,from,to,cursor,limit);}
    @GetMapping("/articles/{id}/proposals") public JsonNode proposals(@PathVariable UUID id,@RequestParam(required=false) String status,@RequestParam(required=false) String cursor,@RequestParam(defaultValue="20") int limit){return proposals.list(ActorContext.current(),id,status,cursor,limit);}
    @PostMapping("/articles/{id}/versions") public void save(@PathVariable UUID id,HttpServletRequest req,HttpServletResponse res)throws Exception{command(id,"save",req,res);}
    @PostMapping("/articles/{id}/restore") public void restore(@PathVariable UUID id,HttpServletRequest req,HttpServletResponse res)throws Exception{command(id,"restore",req,res);}
    @PostMapping("/proposals/{id}/accept") public void accept(@PathVariable UUID id,HttpServletRequest req,HttpServletResponse res)throws Exception{command(id,"accept",req,res);}
    @PostMapping("/proposals/{id}/reject") public void reject(@PathVariable UUID id,HttpServletRequest req,HttpServletResponse res)throws Exception{command(id,"reject",req,res);}
    private static final class Prepare extends RuntimeException {}
    private void command(UUID id,String action,HttpServletRequest req,HttpServletResponse res)throws Exception {
        var actor=ActorContext.current();actor.requireHuman();boolean proposal=action.equals("accept")||action.equals("reject");
        UUID article=proposal?proposals.article(actor,id):id;articles.job(actor,article,false);
        byte[] bytes=req.getInputStream().readNBytes(8*1048576+1);if(bytes.length>8*1048576)fail("BODY_TOO_LARGE");
        try {java.nio.charset.StandardCharsets.UTF_8.newDecoder().onMalformedInput(java.nio.charset.CodingErrorAction.REPORT).decode(java.nio.ByteBuffer.wrap(bytes));}catch(java.nio.charset.CharacterCodingException e){fail("INVALID_UTF8");}
        String etag=req.getHeader("If-Match");var prepared=new ArticleService.PreparedVersion[1];
        java.util.function.Supplier<Idempotency.Response> execute=()->idem.execute(actor,"POST",req.getRequestURI(),req.getQueryString(),req.getHeader("Idempotency-Key"),req.getHeader("X-Request-Hash"),bytes,
            ()->{articles.job(actor,article,true);if(proposal)proposals.read(actor,id,true);},
            ()->{var body=CanonicalRequest.parse(bytes);articles.validate(body,switch(action){case "accept"->"BaseVersionRequest";case "reject"->"ReasonRequest";case "restore"->"RestoreRequest";default->"SaveVersionRequest";});
                if(!action.equals("reject"))versions.guard(actor,article,etag,body.has("baseVersionId")?uuid(body.path("baseVersionId").asText()):null);
                if(proposal)proposals.pending(actor,id,body.has("baseVersionId")?uuid(body.path("baseVersionId").asText()):null);},
            ()->{if(action.equals("reject"))return new Idempotency.Response(200,CanonicalRequest.canonical(proposals.reject(actor,id,CanonicalRequest.parse(bytes))),Map.of("Content-Type","application/json"));
                if(prepared[0]==null)throw new Prepare();UUID version=versions.save(actor,prepared[0]);
                if(action.equals("accept"))proposals.accepted(actor,id,version);proposals.staleOther(actor,article,version);
                return response(201,actor,article,articles.readVersion(actor,article,version));});
        for(int attempt=0;attempt<8;attempt++) {
            try {reply(res,execute.get());return;}
            catch(Prepare e){ /* probe transaction rolled back before staging */ }
            catch(PublicFailure e){if(!e.code().equals("RESTAGE_REQUIRED"))throw e;}
            var body=CanonicalRequest.parse(bytes);
            prepared[0]=null;
            try {prepared[0]=action.equals("accept")?versions.prepareAcceptance(actor,article,uuid(body.path("baseVersionId").asText()),proposals.candidate(actor,id),etag):versions.prepare(actor,article,body,etag,action.equals("restore"));}
            catch(PublicFailure stageFailure) {
                // A concurrent identical command may have committed between the probe and staging.
                // Re-authorize/replay before reporting the now-stale ETag or proposal state.
                try {reply(res,execute.get());return;}catch(Prepare needs){throw stageFailure;}
            }
        }
        throw new PublicFailure(503,"VERSION_CONTENTION");
    }
    private Idempotency.Response response(int status,ActorContext a,UUID article,JsonNode body) {return new Idempotency.Response(status,CanonicalRequest.canonical(body),Map.of("Content-Type","application/json","ETag","\"job-"+articles.job(a,article,false).path("lockVersion").asLong()+"\""));}
    private static void reply(HttpServletResponse res,Idempotency.Response r)throws Exception {res.setStatus(r.status());r.headers().forEach(res::setHeader);res.getOutputStream().write(r.body());}
}
