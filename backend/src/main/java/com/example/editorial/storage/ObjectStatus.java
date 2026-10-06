package com.example.editorial.storage;

/**
 * Backend lifecycle of a stored object. STAGING means written but not yet
 * confirmed referenced by a committed domain row; COMMITTED means the reference
 * transaction committed and completion was marked. DELETED is a tombstone for
 * audit/retention, never a success state returned to callers.
 */
public enum ObjectStatus { STAGING, COMMITTED, DELETED }
