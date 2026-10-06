package com.example.editorial.editorial.skill;

/** Server-allocated semantic version. Parsing and comparison only; allocation rules live in the service. */
public record SemVer(int major, int minor, int patch) implements Comparable<SemVer> {
    public static final SemVer FIRST = new SemVer(1, 0, 0);

    public static SemVer parse(String value) {
        if (value == null) throw new IllegalArgumentException("version is required");
        String[] parts = value.split("\\.", -1);
        if (parts.length != 3) throw new IllegalArgumentException("not a semver");
        try {
            int major = Integer.parseInt(parts[0]);
            int minor = Integer.parseInt(parts[1]);
            int patch = Integer.parseInt(parts[2]);
            if (major < 0 || minor < 0 || patch < 0) throw new IllegalArgumentException("negative component");
            return new SemVer(major, minor, patch);
        } catch (NumberFormatException e) { throw new IllegalArgumentException("not a semver"); }
    }

    public SemVer nextPatch() { return new SemVer(major, minor, patch + 1); }

    @Override public int compareTo(SemVer o) {
        int c = Integer.compare(major, o.major);
        if (c != 0) return c;
        c = Integer.compare(minor, o.minor);
        if (c != 0) return c;
        return Integer.compare(patch, o.patch);
    }

    @Override public String toString() { return major + "." + minor + "." + patch; }
}
