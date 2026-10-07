import java.nio.file.*;
import java.util.*;
import java.util.stream.*;

/** Round-4 reviewer self-check: is the classpath file the probe used actually complete and readable? */
public class CpCheck {
    public static void main(String[] a) throws Exception {
        Path argfile = Paths.get(System.getProperty("user.home"), "AppData/Local/Temp/t08r4/envprobe-cp.txt");
        String text = Files.readString(argfile);
        String cp = text.substring("-cp \"".length(), text.lastIndexOf('"'));
        List<String> parts = Arrays.asList(cp.split(";"));
        System.out.println("entries=" + parts.size());
        long missing = parts.stream().filter(p -> !Files.exists(Paths.get(p))).count();
        System.out.println("missing=" + missing);
        System.out.println("length=" + text.length());
        List<String> interesting = parts.stream().filter(p -> p.contains("spring-test") || p.contains("spring-core")
                || p.contains("spring-boot-3") || p.contains("snakeyaml")).collect(Collectors.toList());
        interesting.forEach(p -> System.out.println("  " + p));
        Path jar = Paths.get(parts.stream().filter(p -> p.contains("spring-test")).findFirst().orElse("none"));
        if (Files.exists(jar)) {
            try (ZipFile zip = new ZipFile(jar.toFile())) {
                Collections.list(zip.entries()).stream()
                        .filter(e -> e.getName().endsWith("MockEnvironment.class"))
                        .forEach(e -> System.out.println("  contains " + e.getName()));
            }
        }
    }
}
