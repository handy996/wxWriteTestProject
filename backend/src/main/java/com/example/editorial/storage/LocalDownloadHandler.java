package com.example.editorial.storage;

import com.example.editorial.shared.ErrorResponses;
import com.example.editorial.shared.PublicFailure;
import com.example.editorial.shared.TraceContext;
import jakarta.servlet.http.HttpServletRequest;
import jakarta.servlet.http.HttpServletResponse;
import java.io.IOException;
import java.time.Clock;
import java.util.List;
import org.springframework.web.HttpRequestHandler;

/** GET-only consumer of five-minute bearer capabilities issued by ObjectStore. */
public final class LocalDownloadHandler implements HttpRequestHandler {
    public static final String PATH = "/api/v1/storage/objects/";
    private final LocalStorageBackend backend;
    private final List<ObjectRefRegistry> registries;
    private final Clock clock;

    public LocalDownloadHandler(LocalStorageBackend backend, List<ObjectRefRegistry> registries, Clock clock) {
        this.backend = backend;
        this.registries = List.copyOf(registries);
        this.clock = clock;
    }

    @Override public void handleRequest(HttpServletRequest request, HttpServletResponse response) throws IOException {
        // This capability route does not enter identity's session filter chain.
        // Generate a trusted trace locally rather than trusting a client header.
        var traceId = java.util.UUID.randomUUID();
        try (var ignored = TraceContext.open(traceId)) {
            response.setHeader("X-Trace-Id", traceId.toString());
            serve(request, response);
        }
    }

    private void serve(HttpServletRequest request, HttpServletResponse response) throws IOException {
        try {
            if (!"GET".equals(request.getMethod())) throw new PublicFailure(405, "METHOD_NOT_ALLOWED");
            String path = request.getRequestURI().substring(request.getContextPath().length());
            if (!path.startsWith(PATH)) throw new PublicFailure(404, "NOT_FOUND");
            String key = path.substring(PATH.length());
            try { ObjectKeys.requireValid(key); }
            catch (IllegalArgumentException e) { throw new PublicFailure(403, "INVALID_DOWNLOAD_LINK"); }
            byte[] bytes = backend.download(path + "?" + request.getQueryString(), clock.instant());
            ObjectRefRegistry.Resolution found = null;
            for (ObjectRefRegistry registry : registries) {
                var resolution = registry.resolve(key);
                if (resolution == null) continue;
                if (resolution.revoked() || (found != null && !found.articleId().equals(resolution.articleId())))
                    throw new PublicFailure(404, "OBJECT_REVOKED");
                found = resolution;
            }
            if (found == null) throw new PublicFailure(404, "NOT_FOUND");
            response.setContentType("application/octet-stream");
            response.setHeader("Content-Disposition", "attachment; filename=\"" + key + "\"");
            response.setHeader("Cache-Control", "no-store");
            response.setHeader("X-Content-Type-Options", "nosniff");
            response.setContentLengthLong(bytes.length);
            response.getOutputStream().write(bytes);
        } catch (PublicFailure failure) {
            ErrorResponses.write(response, failure);
        } catch (RuntimeException failure) {
            ErrorResponses.write(response, new PublicFailure(503, "OBJECT_READ_FAILED"));
        }
    }
}
