package com.example.editorial.article.job;

import com.example.editorial.shared.*;
import com.example.editorial.article.ast.ArticleAst;
import com.fasterxml.jackson.databind.JsonNode;
import jakarta.servlet.http.*;
import java.util.*;
import org.springframework.boot.autoconfigure.condition.ConditionalOnProperty;
import org.springframework.web.bind.annotation.*;

@RestController
@RequestMapping("/api/v1/articles")
@ConditionalOnProperty(name="editorial.article.enabled",havingValue="true")
public final class ArticleController {
    private final ArticleService articles;
    private final Idempotency idem;
    private final ArticlePorts.Deletion deletion;
    public ArticleController(ArticleService articles,Idempotency idem,ArticlePorts.Deletion deletion) {this.articles=articles;this.idem=idem;this.deletion=deletion;}
    @GetMapping public JsonNode list(@RequestParam(required=false) String status,@RequestParam(required=false) String query,@RequestParam(required=false) String cursor,@RequestParam(defaultValue="20") int limit) {return articles.list(ActorContext.current(),status,query,cursor,limit);}
    @GetMapping("/{id}") public void get(@PathVariable UUID id,HttpServletResponse res)throws Exception {reply(res,response(200,articles.artifact(ActorContext.current(),id)));}
    @PostMapping public void create(HttpServletRequest req,HttpServletResponse res)throws Exception {command(null,"create",req,res);}
    @PatchMapping("/{id}") public void patch(@PathVariable UUID id,HttpServletRequest req,HttpServletResponse res)throws Exception {command(id,"patch",req,res);}
    @PostMapping("/{id}/clone") public void cloneArticle(@PathVariable UUID id,HttpServletRequest req,HttpServletResponse res)throws Exception {command(id,"clone",req,res);}
    private void command(UUID id,String action,HttpServletRequest req,HttpServletResponse res)throws Exception {
        var actor=ActorContext.current(); actor.requireHuman(); byte[] bytes=body(req);
        if(id!=null) articles.job(actor,id,false);
        var prepared=new ArticleService.PreparedOriginal[1];
        java.util.function.Supplier<Idempotency.Response> execute=()->idem.execute(actor,req.getMethod(),req.getRequestURI(),req.getQueryString(),req.getHeader("Idempotency-Key"),req.getHeader("X-Request-Hash"),bytes,
            ()->{if(id!=null) articles.job(actor,id,true);},
            ()->{if(id!=null && action.equals("patch")) Idempotency.requireEtag(req.getHeader("If-Match"),articles.job(actor,id,true).path("lockVersion").asLong());},
            ()->{ var body=CanonicalRequest.parse(bytes); UUID resultId=id;
                if(!action.equals("patch") && prepared[0]==null) throw new NeedsPreparation();
                if(action.equals("create")) resultId=articles.create(actor,body,prepared[0]);
                else if(action.equals("clone")) resultId=articles.cloneArticle(actor,id,body,prepared[0]);
                else articles.patch(actor,id,body);
                return response(action.equals("patch")?200:201,articles.artifact(actor,resultId)); });
        Idempotency.Response result;
        try {result=execute.get();} catch(NeedsPreparation e) {
            // Probe rolls back without a record; final execution repeats authorization, lock, replay and conditions.
            var parsed=CanonicalRequest.parse(bytes);
            prepared[0]=action.equals("create")?articles.prepareCreate(actor,parsed):articles.prepareClone(actor,id,parsed);
            result=execute.get();
        }
        reply(res,result);
    }
    private static final class NeedsPreparation extends RuntimeException {}
    @GetMapping("/{id}/deletion-impact") public JsonNode impact(@PathVariable UUID id) {
        var actor=ActorContext.current(); articles.job(actor,id,false); return deletion.preview(actor,id);
    }
    @PostMapping("/{id}/deletion") public void delete(@PathVariable UUID id,HttpServletRequest req,HttpServletResponse res)throws Exception {
        var actor=ActorContext.current(); actor.requireHuman(); articles.job(actor,id,false); byte[] bytes=body(req);
        articles.validate(CanonicalRequest.parse(bytes),"DeleteArticleRequest");
        // The durable command adapter owns authorization -> replay -> ETag validation, short DB transaction,
        // out-of-transaction REQUESTED journal append, receipt persistence, and only then the 202 response.
        reply(res,deletion.submit(actor,id,req.getRequestURI(),req.getQueryString(),req.getHeader("Idempotency-Key"),req.getHeader("X-Request-Hash"),req.getHeader("If-Match"),bytes));
    }
    private static byte[] body(HttpServletRequest req)throws Exception {
        // JSON can escape each input code point to six bytes; actual content is checked separately at 1 MiB.
        byte[] bytes=req.getInputStream().readNBytes(8*1048576+1); if(bytes.length>8*1048576) throw new PublicFailure(422,"BODY_TOO_LARGE");
        // Strict decoding rejects UTF-16 JSON auto-detection as well as malformed UTF-8.
        try { java.nio.charset.StandardCharsets.UTF_8.newDecoder().onMalformedInput(java.nio.charset.CodingErrorAction.REPORT).decode(java.nio.ByteBuffer.wrap(bytes)); }
        catch(java.nio.charset.CharacterCodingException e) {throw new PublicFailure(422,"INVALID_UTF8");} return bytes;
    }
    static Idempotency.Response response(int status,JsonNode body) {
        var headers=new HashMap<String,String>(); headers.put("Content-Type","application/json"); headers.put("ETag","\"job-"+body.path("job").path("lockVersion").asLong()+"\"");
        if(status==201) headers.put("Location","/api/v1/articles/"+body.path("job").path("id").asText());
        return new Idempotency.Response(status,CanonicalRequest.canonical(body),headers);
    }
    private static void reply(HttpServletResponse res,Idempotency.Response r)throws Exception {res.setStatus(r.status());r.headers().forEach(res::setHeader);res.getOutputStream().write(r.body());}
}
