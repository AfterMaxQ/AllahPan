# AllahPan Backend Full Review & E2E Stability Test Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Complete end-to-end review of all backend logic, identify bugs, verify all 31 API endpoints, and test system stability under edge cases.

**Architecture:** Two-phase approach. Phase 1: Static code review of all 31 source files to identify bugs, logic flaws, and edge cases. Phase 2: Runtime verification — start infrastructure, run targeted curl/API tests against every endpoint, validate the upload→process→search pipeline, and stress-test error handling.

**Tech Stack:** Spring Boot 3.5 + Java 17 + MyBatis + MySQL:3307 + Redis:6379 + RabbitMQ:5672 + MinIO:9000 + ES:9200 + Ollama:11434

---

## Phase 1: Static Code Review — Bug Hunt

### Task 1: Auth & Security Review

**Files:**
- Review: `allahpan-core/src/main/java/com/allahpan/controller/AuthController.java`
- Review: `allahpan-core/src/main/java/com/allahpan/service/impl/AuthCodeServiceImpl.java`
- Review: `allahpan-core/src/main/java/com/allahpan/service/impl/UserServiceImpl.java`
- Review: `allahpan-security/src/main/java/com/allahpan/security/config/SecurityConfig.java`
- Review: `allahpan-security/src/main/java/com/allahpan/security/component/JwtAuthenticationTokenFilter.java`

- [ ] **Step 1: Verify rate limiting correctness**

Check Redis keys pattern for auth code flow:
```
allahpan:authCode:{email}     → 5min TTL (verification code)
allahpan:sendLimit:{email}    → 30s TTL (send interval)
allahpan:attempts:{email}     → 1h TTL (attempt counter)
```
Verify: sendCode checks sendLimit BEFORE generating code (prevents code overwrite).
Verify: verifyCode doesn't reset attempts counter on success (preserves hour-limit).

- [ ] **Step 2: Check login-by-code code presence validation**

Read `LoginRequest.java`. Does `loginByCode` endpoint check that `code` is not blank? The controller calls `verifyCode(req.getEmail(), req.getCode())` — if `req.getCode()` is null, verifyCode will compare null with stored code and fail with CODE_ERROR. This is acceptable but should be explicitly validated.

- [ ] **Step 3: Check auto-registration security**

`loginByCode` auto-registers if email not found. Verify:
- No password is set on auto-register (firstLogin=1)
- User can't login by password until password is set
- Nickname derived from email prefix (what if email has no @?)

- [ ] **Step 4: Verify JWT token refresh logic**

Check `JwtTokenUtil.canRefresh` and `refreshToken`. The token refresh only works within 30min of expiry. Verify the refresh endpoint exists or document its absence.

- [ ] **Step 5: Check security filter chain completeness**

All `/api/share/**` paths are public. Verify:
- `/api/share/{code}` GET is public ✓
- `/api/share/{code}` DELETE requires auth ✓ (separate path with same prefix — is it handled correctly? SecurityConfig has `/api/share/**` as permitAll, so DELETE `/api/share/{code}` is ALSO public! This is a BUG — anyone can delete anyone's share link.)

**Expected findings to document:**
- BUG: `SecurityConfig` permits `/api/share/**` to all — DELETE `/api/share/{code}` is unprotected
- MINOR: `loginByCode` doesn't explicitly validate code is non-null before verifyCode
- MINOR: Auto-register nickname extraction assumes email contains `@`

---

### Task 2: File Service Logic Review

**Files:**
- Review: `allahpan-core/src/main/java/com/allahpan/service/impl/FileServiceImpl.java`

- [ ] **Step 1: Upload flow review**

Trace the full upload path:
1. Validate parent folder exists and is folder
2. Validate filename not blank, not too long
3. Resolve relative path from parent chain
4. Resolve filesystem conflicts (append counter)
5. Stream to disk + calculate MD5
6. MD5 dedup check (second-pass)
7. Insert DB record with process_status=0

Issues to check:
- What if parent chain traversal hits a cycle?
- `resolveConflict` loop could be infinite if disk is full/corrupt
- MD5 dedup only checks `andDeleteTimeIsNull()` — correct
- `detectFileType` for Office documents only matches specific MIME types; what about `application/vnd.openxmlformats-officedocument.wordprocessingml.document` vs the actual MIME from browser?

- [ ] **Step 2: Delete flow review**

Trace delete:
1. Set delete_time
2. updateByPrimaryKeySelective
3. moveToTrash (local disk)
4. ES delete (if not folder)
5. Recursive deleteChildren

Issues:
- `moveToTrash` only moves non-folders — folders are NOT moved to trash (their storageKey is a relative path, FileServiceImpl.moveToTrash only handles non-folders). This means folder storageKey entries in .trash/ are orphaned.
- Recursion depth unbounded — StackOverflowError for deep trees
- No transactional boundary — if ES delete fails, DB is already updated

- [ ] **Step 3: Restore flow review**

`restoreFile`: clears deleteTime, restores from .trash, re-indexes to ES. Recursive for folders.
Issue: `restoreChildren` queries `andDeleteTimeIsNotNull()` — correct. But what about partially deleted trees where some children were deleted independently?

- [ ] **Step 4: Rename & Move path rebuilding**

Both `renameFile` and `moveFile` call `rebuildDescendantPaths` for folders. This recursively walks children and calls `buildPath` which walks up the parent chain. O(n²) complexity for deep trees.

- [ ] **Step 5: Missing @Transactional**

None of the multi-step operations use transactions. If any step fails mid-way, the DB could be left in an inconsistent state.

- [ ] **Step 6: listTrash shows ALL users' trash**

`listTrash` has no `uploaderId` filter — all users see all trash. Privacy issue.

- [ ] **Step 7: batchDelete lacks transaction**

If 3 of 10 deletes succeed, 3 files are already soft-deleted. No rollback.

---

### Task 3: Pipeline & Component Review

**Files:**
- Review: `allahpan-core/src/main/java/com/allahpan/component/FileProcessReceiver.java`
- Review: `allahpan-core/src/main/java/com/allahpan/component/FileProcessSender.java`
- Review: `allahpan-core/src/main/java/com/allahpan/component/EsIndexServiceImpl.java`
- Review: `allahpan-core/src/main/java/com/allahpan/component/FileSystemWatcher.java`
- Review: `allahpan-core/src/main/java/com/allahpan/component/ThumbnailGenerator.java`
- Review: `allahpan-core/src/main/java/com/allahpan/component/TextExtractor.java`

- [ ] **Step 1: FileProcessReceiver retry logic**

Verify exponential backoff: 30s → 60s → 120s → exhausted.
Check: `isInfrastructureError` method — the last condition `e instanceof RuntimeException && e.getMessage() != null && (e.getMessage().contains("缩略图") || e.getMessage().contains("OCR"))` could mask non-infrastructure RuntimeExceptions.

- [ ] **Step 2: FileSystemWatcher thread safety**

Check:
- `pendingPaths` is ConcurrentHashMap.newKeySet() — correct
- `emitters` is CopyOnWriteArrayList — correct
- `notifyAll` iterates without synchronization — CopyOnWriteArrayList is safe for iteration during modification
- `reconcilePending` creates snapshot with `new HashSet<>(pendingPaths)` then clears — potential race: a new path added between snapshot and clear is lost

- [ ] **Step 3: EsIndexServiceImpl.rebuildAll uses wrong select method**

`rebuildAll()` uses `fileMapper.selectByExample(example)` which does NOT load `originText` (LONGTEXT/BLOB). Must use `selectByExampleWithBLOBs`. This means ES rebuild loses all extracted text, making search useless after rebuild.

- [ ] **Step 4: FileSystemWatcher OOM risk**

`ensureFileInDb` → `calculateMd5` calls `Files.readAllBytes(filePath)` — loads entire file into memory. For large files (up to 512MB upload limit), this will cause OOM.

- [ ] **Step 5: FileSystemWatcher uploaderId hardcoded to 1L**

Both `ensureFolderInDb` and `ensureFileInDb` set `uploaderId = 1L`. Files created via filesystem events are attributed to user 1.

- [ ] **Step 6: ThumbnailGenerator & TextExtractor read entire file into memory**

Both call `is.readAllBytes()` — loads entire file. OK for thumbnails (images) but potentially problematic for large documents.

---

### Task 4: Controller & API Surface Review

**Files:**
- Review: `allahpan-core/src/main/java/com/allahpan/controller/FileController.java`
- Review: `allahpan-core/src/main/java/com/allahpan/controller/ShareController.java`
- Review: `allahpan-core/src/main/java/com/allahpan/controller/FavoriteController.java`
- Review: `allahpan-core/src/main/java/com/allahpan/controller/SearchController.java`
- Review: `allahpan-core/src/main/java/com/allahpan/controller/UserController.java`

- [ ] **Step 1: Check input validation coverage**

Every endpoint that accepts user input:
- `/api/file/upload`: parentId, file — validated in service
- `/api/file/create-folder`: folderName, parentId — validated
- `/api/file/{fileId}/rename`: newName — validated
- `/api/file/{fileId}/move`: targetParentId — validated
- `/api/file/batch`: fileIds — NOT validated for empty list
- `/api/share/{fileId}`: expireHours — validated (1-168)
- `/api/search`: keyword — required but NOT validated for blank
- `/api/user/set-password`: newPassword — @NotBlank validated

- [ ] **Step 2: Check response consistency**

All controllers use `CommonResult<T>`. Verify:
- Success responses include data
- Error responses include message
- FileController.toFileResponse includes all fields

- [ ] **Step 3: Check public endpoints are truly public**

Public endpoints per SecurityConfig:
- `/api/share/**` — but this includes DELETE! (Bug noted above)
- `/api/file/*/thumbnail` — GET, public ✓
- `/api/file/*/stream` — GET, public ✓
- `/api/file/*/download` — GET, public ✓
- `/api/file/watch` — SSE, token via query param ✓

- [ ] **Step 4: FavoriteService missing file existence check**

`addFavorite(fileId)` doesn't verify the file exists. User can favorite non-existent files.

- [ ] **Step 5: SearchController creates new RestTemplate per request**

`new RestTemplate()` per search call — should reuse or inject as bean.

---

### Task 5: Document all findings

- [ ] **Step 1: Compile bug list**

Write a summary markdown document at `docs/superpowers/plans/2026-06-09-findings.md` listing all bugs found above, categorized by severity:
- **P0 (Critical):** Data loss, security bypass, OOM
- **P1 (High):** Feature broken, data inconsistency
- **P2 (Medium):** Privacy, performance, missing validation
- **P3 (Low):** Code quality, edge cases

See Appendix A for the compiled findings.

---

## Phase 2: Runtime Verification

### Prerequisites

- [ ] **Step 1: Verify all infrastructure is running**

```bash
docker compose up -d
```

Check each service:
```bash
# MySQL
docker exec allahpan-mysql mysql -uroot -p123456 -e "SELECT 1" allahpan

# Redis
docker exec allahpan-redis redis-cli ping

# RabbitMQ
curl -s -u guest:guest http://localhost:15672/api/aliveness-test/%2F

# MinIO
curl -s http://localhost:9000/minio/health/live

# Elasticsearch
curl -s http://localhost:9200/_cluster/health

# Ollama
curl -s http://localhost:11434/api/tags
```

Expected: All return success/healthy status.

---

- [ ] **Step 2: Build and start backend services**

```bash
mvn clean install -pl allahpan-common,allahpan-mbg,allahpan-security,allahpan-core,allahpan-search -DskipTests
```

Start core (background):
```bash
mvn spring-boot:run -pl allahpan-core &
```

Start search (background):
```bash
mvn spring-boot:run -pl allahpan-search &
```

Wait for both to be ready:
```bash
# Wait for core
until curl -s http://localhost:8088/api/auth/send-code -X POST -H "Content-Type: application/json" -d '{"email":"test@test.com"}' > /dev/null 2>&1; do sleep 1; done; echo "Core ready"

# Wait for search
until curl -s http://localhost:8081/es-admin/files/search?keyword=__health__ > /dev/null 2>&1; do sleep 1; done; echo "Search ready"
```

---

### Task 6: Auth Flow E2E Test

- [ ] **Step 1: Test send-code rate limiting**

```bash
# First send — should succeed
curl -s -X POST http://localhost:8088/api/auth/send-code \
  -H "Content-Type: application/json" \
  -d '{"email":"test@allahpan.dev"}'

# Second send within 30s — should fail with CODE_SEND_LIMIT
curl -s -X POST http://localhost:8088/api/auth/send-code \
  -H "Content-Type: application/json" \
  -d '{"email":"test@allahpan.dev"}'
```

Expected: First returns `{"code":200,"message":"验证码已发送"}`. Second returns error with code 429.

- [ ] **Step 2: Test verify code failure and attempt limiting**

```bash
# Verify with wrong code 51 times (exceed hourly limit)
for i in $(seq 1 51); do
  echo "Attempt $i:"
  curl -s -X POST http://localhost:8088/api/auth/login-by-code \
    -H "Content-Type: application/json" \
    -d '{"email":"test@allahpan.dev","code":"000000"}'
done
```

Expected: After 50 failures, returns TOO_MANY_REQUESTS (429).

Note: This test requires the auth code to be expired/nonexistent, and we need to send a code first, then intentionally fail. Since we can't read the code from Redis directly, we'll test by sending wrong codes.

- [ ] **Step 3: Test login-by-code success (auto-register)**

First send a code, then extract it from Redis:
```bash
# Send code
curl -s -X POST http://localhost:8088/api/auth/send-code \
  -H "Content-Type: application/json" \
  -d '{"email":"e2e-test@allahpan.dev"}'

# Read code from Redis
docker exec allahpan-redis redis-cli GET "allahpan:authCode:e2e-test@allahpan.dev"

# Login with code
CODE="<paste-from-above>"
curl -s -X POST http://localhost:8088/api/auth/login-by-code \
  -H "Content-Type: application/json" \
  -d "{\"email\":\"e2e-test@allahpan.dev\",\"code\":\"$CODE\"}"
```

Expected: Returns token, userId, email, hasPassword=false, firstLogin=true. New user auto-created in DB.

- [ ] **Step 4: Test set-password and re-login**

```bash
# Extract token from login response
TOKEN="<token-from-step-3>"

# Set password
curl -s -X POST http://localhost:8088/api/user/set-password \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $TOKEN" \
  -d '{"newPassword":"Test123456"}'

# Login by password
curl -s -X POST http://localhost:8088/api/auth/login-by-password \
  -H "Content-Type: application/json" \
  -d '{"email":"e2e-test@allahpan.dev","password":"Test123456"}'
```

Expected: First returns new token with hasPassword=true. Second returns successful login.

- [ ] **Step 5: Test /api/user/me**

```bash
curl -s http://localhost:8088/api/user/me \
  -H "Authorization: Bearer $TOKEN"
```

Expected: Returns user object with password=null.

---

### Task 7: File CRUD E2E Test

- [ ] **Step 1: Create test folders**

```bash
TOKEN="<valid-jwt>"

# Create folder at root
curl -s -X POST http://localhost:8088/api/file/create-folder \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"folderName":"E2E-Test-Folder","parentId":0}'
# Save the returned folder ID as FOLDER_ID

# Create subfolder
curl -s -X POST http://localhost:8088/api/file/create-folder \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d "{\"folderName\":\"SubFolder\",\"parentId\":$FOLDER_ID}"
```

Expected: Both return success with folder objects.

- [ ] **Step 2: Test list files at root**

```bash
curl -s "http://localhost:8088/api/file/list?parentId=0" \
  -H "Authorization: Bearer $TOKEN"
```

Expected: Returns list including "E2E-Test-Folder". Folders first, then files.

- [ ] **Step 3: Test upload file**

Create a test file:
```bash
echo "Hello AllahPan E2E Test - $(date)" > /tmp/e2e-test.txt
```

Upload:
```bash
curl -s -X POST http://localhost:8088/api/file/upload \
  -H "Authorization: Bearer $TOKEN" \
  -F "file=@/tmp/e2e-test.txt" \
  -F "parentId=0"
# Save FILE_ID
```

Expected: Returns file object with processStatus=0 (pending).

- [ ] **Step 4: Test upload image (triggers thumbnail pipeline)**

```bash
# Create a small test JPEG (or use any local image)
curl -s -X POST http://localhost:8088/api/file/upload \
  -H "Authorization: Bearer $TOKEN" \
  -F "file=@/path/to/test-image.jpg" \
  -F "parentId=0"
# Save IMAGE_FILE_ID
```

Wait 5 seconds for processing, then check:
```bash
curl -s "http://localhost:8088/api/file/$IMAGE_FILE_ID" \
  -H "Authorization: Bearer $TOKEN"
```

Expected: processStatus should have progressed (1, 2, or 3). If Ollama is available, should reach 3 with originText populated.

- [ ] **Step 5: Test thumbnail access**

```bash
curl -s -o /dev/null -w "%{http_code}" \
  "http://localhost:8088/api/file/$IMAGE_FILE_ID/thumbnail"
```

Expected: 200 (if thumbnail generated) or 404 (if not yet processed).

- [ ] **Step 6: Test file download**

```bash
curl -s -o /tmp/e2e-downloaded.txt \
  -H "Authorization: Bearer $TOKEN" \
  "http://localhost:8088/api/file/$FILE_ID/download"
# Verify content matches
diff /tmp/e2e-test.txt /tmp/e2e-downloaded.txt && echo "MATCH" || echo "MISMATCH"
```

Expected: MATCH.

- [ ] **Step 7: Test file stream (inline preview)**

```bash
curl -s -o /tmp/e2e-streamed.txt \
  "http://localhost:8088/api/file/$FILE_ID/stream"
diff /tmp/e2e-test.txt /tmp/e2e-streamed.txt && echo "MATCH" || echo "MISMATCH"
```

Expected: MATCH. Content is served inline.

---

### Task 8: File Operations E2E Test

- [ ] **Step 1: Test rename**

```bash
curl -s -X PUT "http://localhost:8088/api/file/$FILE_ID/rename" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"newName":"e2e-renamed.txt"}'
```

Expected: Returns file with new name, storageKey updated.

- [ ] **Step 2: Test move**

```bash
curl -s -X PUT "http://localhost:8088/api/file/$FILE_ID/move" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d "{\"targetParentId\":$FOLDER_ID}"
```

Expected: Returns file with new parentId and filePath.

Move it back:
```bash
curl -s -X PUT "http://localhost:8088/api/file/$FILE_ID/move" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"targetParentId":0}'
```

- [ ] **Step 3: Test breadcrumb navigation**

```bash
curl -s "http://localhost:8088/api/file/tree/$FOLDER_ID" \
  -H "Authorization: Bearer $TOKEN"
```

Expected: Returns array of folders from root to FOLDER_ID.

- [ ] **Step 4: Test soft delete**

```bash
curl -s -X DELETE "http://localhost:8088/api/file/$FILE_ID" \
  -H "Authorization: Bearer $TOKEN"
```

Expected: Success. File now has deleteTime set.

- [ ] **Step 5: Test trash listing**

```bash
curl -s "http://localhost:8088/api/file/trash?pageNum=1&pageSize=20" \
  -H "Authorization: Bearer $TOKEN"
```

Expected: Returns list of deleted files including the one we just deleted.

- [ ] **Step 6: Test restore from trash**

```bash
curl -s -X PUT "http://localhost:8088/api/file/trash/$FILE_ID/restore" \
  -H "Authorization: Bearer $TOKEN"
```

Expected: Success. File is back in original location.

- [ ] **Step 7: Test permanent delete**

```bash
# Soft delete first
curl -s -X DELETE "http://localhost:8088/api/file/$FILE_ID" \
  -H "Authorization: Bearer $TOKEN"

# Then permanent delete
curl -s -X DELETE "http://localhost:8088/api/file/trash/$FILE_ID" \
  -H "Authorization: Bearer $TOKEN"
```

Expected: Success. File no longer in DB.

- [ ] **Step 8: Test batch delete**

```bash
# Create 3 test files
for i in 1 2 3; do
  echo "batch test $i" > "/tmp/e2e-batch-$i.txt"
  curl -s -X POST http://localhost:8088/api/file/upload \
    -H "Authorization: Bearer $TOKEN" \
    -F "file=@/tmp/e2e-batch-$i.txt" \
    -F "parentId=0"
done
# Collect IDs as BATCH_IDS

# Batch delete
curl -s -X DELETE "http://localhost:8088/api/file/batch" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"fileIds":[BATCH_ID1, BATCH_ID2, BATCH_ID3]}'
```

Expected: Returns {deletedCount: 3, failedIds: []}.

---

### Task 9: Share & Favorite E2E Test

- [ ] **Step 1: Create a file for sharing**

```bash
echo "Share test file" > /tmp/e2e-share.txt
SHARE_RESP=$(curl -s -X POST http://localhost:8088/api/file/upload \
  -H "Authorization: Bearer $TOKEN" \
  -F "file=@/tmp/e2e-share.txt" \
  -F "parentId=0")
SHARE_FILE_ID=$(echo $SHARE_RESP | jq -r '.data.id')
```

- [ ] **Step 2: Create share link**

```bash
SHARE_RESP=$(curl -s -X POST "http://localhost:8088/api/share/$SHARE_FILE_ID?expireHours=24" \
  -H "Authorization: Bearer $TOKEN")
SHARE_CODE=$(echo $SHARE_RESP | jq -r '.data.shareCode')
```

Expected: Returns shareCode (8 chars), shareUrl, expireTime.

- [ ] **Step 3: Access share link (public, no auth)**

```bash
curl -s "http://localhost:8088/api/share/$SHARE_CODE"
```

Expected: Returns fileId, fileName, fileSize, downloadUrl, createTime. No auth required.

- [ ] **Step 4: Test share link expiration**

Create a share with expireHours=1, then wait and verify:
```bash
# Can't wait 1 hour in test — verify Redis TTL instead
docker exec allahpan-redis redis-cli TTL "allahpan:share:$SHARE_CODE"
```

Expected: TTL is approximately 3600 + 3600 = 7200 seconds (expireHours + 1h buffer).

- [ ] **Step 5: Test delete share**

```bash
curl -s -X DELETE "http://localhost:8088/api/share/$SHARE_CODE" \
  -H "Authorization: Bearer $TOKEN"

# Verify it's gone
curl -s "http://localhost:8088/api/share/$SHARE_CODE"
```

Expected: After delete, accessing share returns error.

- [ ] **Step 6: Test favorites flow**

```bash
# Add favorite
curl -s -X POST "http://localhost:8088/api/favorite/$SHARE_FILE_ID" \
  -H "Authorization: Bearer $TOKEN"

# Check is favorited
curl -s "http://localhost:8088/api/favorite/check/$SHARE_FILE_ID" \
  -H "Authorization: Bearer $TOKEN"
# Expected: {"data": true}

# List favorites
curl -s "http://localhost:8088/api/favorite/list?pageNum=1&pageSize=20" \
  -H "Authorization: Bearer $TOKEN"

# Remove favorite
curl -s -X DELETE "http://localhost:8088/api/favorite/$SHARE_FILE_ID" \
  -H "Authorization: Bearer $TOKEN"

# Verify removed
curl -s "http://localhost:8088/api/favorite/check/$SHARE_FILE_ID" \
  -H "Authorization: Bearer $TOKEN"
# Expected: {"data": false}
```

- [ ] **Step 7: Test idempotent favorite**

```bash
# Add same favorite twice
curl -s -X POST "http://localhost:8088/api/favorite/$SHARE_FILE_ID" \
  -H "Authorization: Bearer $TOKEN"
curl -s -X POST "http://localhost:8088/api/favorite/$SHARE_FILE_ID" \
  -H "Authorization: Bearer $TOKEN"
# Both should succeed (second is no-op)
```

Expected: Both return success.

---

### Task 10: Search E2E Test

- [ ] **Step 1: Create file with searchable content**

```bash
echo "AllahPan is a shared cloud drive system built with Spring Boot" > /tmp/e2e-search.txt
SEARCH_RESP=$(curl -s -X POST http://localhost:8088/api/file/upload \
  -H "Authorization: Bearer $TOKEN" \
  -F "file=@/tmp/e2e-search.txt" \
  -F "parentId=0")
SEARCH_FILE_ID=$(echo $SEARCH_RESP | jq -r '.data.id')
```

- [ ] **Step 2: Wait for processing pipeline**

Poll the file status until process_status=3:
```bash
for i in $(seq 1 30); do
  STATUS=$(curl -s "http://localhost:8088/api/file/$SEARCH_FILE_ID" \
    -H "Authorization: Bearer $TOKEN" | jq -r '.data.processStatus')
  echo "Status: $STATUS"
  if [ "$STATUS" = "3" ]; then break; fi
  sleep 2
done
```

- [ ] **Step 3: Search by keyword**

```bash
curl -s "http://localhost:8088/api/search?keyword=cloud+drive&pageNum=1&pageSize=10" \
  -H "Authorization: Bearer $TOKEN"
```

Expected: Returns search results containing the file.

- [ ] **Step 4: Search with file type filter**

```bash
curl -s "http://localhost:8088/api/search?keyword=AllahPan&fileType=DOCUMENT&pageNum=1&pageSize=10" \
  -H "Authorization: Bearer $TOKEN"
```

- [ ] **Step 5: Test search with no results**

```bash
curl -s "http://localhost:8088/api/search?keyword=xyznonexistent12345&pageNum=1&pageSize=10" \
  -H "Authorization: Bearer $TOKEN"
```

Expected: Returns empty list, no error.

- [ ] **Step 6: Test rebuild-index**

```bash
curl -s -X POST "http://localhost:8088/api/search/rebuild-index" \
  -H "Authorization: Bearer $TOKEN"
```

Expected: Returns {indexedCount: N} where N >= number of active files.

---

### Task 11: Error Handling & Edge Cases

- [ ] **Step 1: Test 401 on unauthenticated requests**

```bash
# Try accessing protected endpoint without token
curl -s -o /dev/null -w "%{http_code}" \
  "http://localhost:8088/api/file/list?parentId=0"
```

Expected: 200 with JSON body containing code 401 (RestAuthenticationEntryPoint returns HTTP 200 + JSON).

- [ ] **Step 2: Test 401 with invalid token**

```bash
curl -s "http://localhost:8088/api/file/list?parentId=0" \
  -H "Authorization: Bearer invalid-token-here"
```

Expected: Returns unauthorized JSON.

- [ ] **Step 3: Test folder name uniqueness**

```bash
# Create first folder
curl -s -X POST http://localhost:8088/api/file/create-folder \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"folderName":"UniqueTest","parentId":0}'

# Try creating duplicate
curl -s -X POST http://localhost:8088/api/file/create-folder \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"folderName":"UniqueTest","parentId":0}'
```

Expected: Second request returns error "同名文件或文件夹已存在".

- [ ] **Step 4: Test upload with empty filename**

```bash
curl -s -X POST http://localhost:8088/api/file/upload \
  -H "Authorization: Bearer $TOKEN" \
  -F "file=@/dev/null;filename=" \
  -F "parentId=0"
```

Expected: Error "文件名不能为空".

- [ ] **Step 5: Test move folder into itself**

```bash
# Try to move a folder to be its own child
curl -s -X PUT "http://localhost:8088/api/file/$FOLDER_ID/move" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d "{\"targetParentId\":$FOLDER_ID}"
```

Expected: Error "不能移动到自身".

- [ ] **Step 6: Test restore file whose parent is in trash**

```bash
# Create folder, create file inside, delete folder, try restore file
# This should fail because parent is still in trash
```

Expected: Error "父文件夹在垃圾站中，请先恢复父文件夹".

- [ ] **Step 7: Test file not found**

```bash
curl -s "http://localhost:8088/api/file/999999" \
  -H "Authorization: Bearer $TOKEN"
```

Expected: Returns null data or error. Verify behavior.

- [ ] **Step 8: Test SSE watch endpoint**

```bash
# Connect to SSE with valid token
curl -s -N "http://localhost:8088/api/file/watch?token=$TOKEN" &
SSE_PID=$!
sleep 2

# Upload a file to trigger SSE event
curl -s -X POST http://localhost:8088/api/file/upload \
  -H "Authorization: Bearer $TOKEN" \
  -F "file=@/tmp/e2e-test.txt" \
  -F "parentId=0"

sleep 3
kill $SSE_PID 2>/dev/null
```

Expected: SSE receives "connected" event, then file-created events.

- [ ] **Step 9: Test SSE with invalid token**

```bash
curl -s "http://localhost:8088/api/file/watch?token=invalid"
```

Expected: SSE completes with error immediately.

---

### Task 12: Stability & Stress Tests

- [ ] **Step 1: Upload 50 files in rapid succession**

```bash
for i in $(seq 1 50); do
  echo "Stress test file $i" > "/tmp/e2e-stress-$i.txt"
  curl -s -X POST http://localhost:8088/api/file/upload \
    -H "Authorization: Bearer $TOKEN" \
    -F "file=@/tmp/e2e-stress-$i.txt" \
    -F "parentId=0" &
done
wait

# Check how many were created
curl -s "http://localhost:8088/api/file/list?parentId=0" \
  -H "Authorization: Bearer $TOKEN" | jq '.data | length'
```

Expected: All 50 created. No server errors.

- [ ] **Step 2: Create deep folder hierarchy**

```bash
PARENT=0
for i in $(seq 1 20); do
  RESP=$(curl -s -X POST http://localhost:8088/api/file/create-folder \
    -H "Authorization: Bearer $TOKEN" \
    -H "Content-Type: application/json" \
    -d "{\"folderName\":\"Level-$i\",\"parentId\":$PARENT}")
  PARENT=$(echo $RESP | jq -r '.data.id')
done

# Test breadcrumb on deepest folder
curl -s "http://localhost:8088/api/file/tree/$PARENT" \
  -H "Authorization: Bearer $TOKEN" | jq '.data | length'
```

Expected: 20 entries in breadcrumb trail.

- [ ] **Step 3: Test recursive delete of deep hierarchy**

```bash
# Delete the root level-1 folder (should cascade)
LEVEL1_ID="<first folder id>"
curl -s -X DELETE "http://localhost:8088/api/file/$LEVEL1_ID" \
  -H "Authorization: Bearer $TOKEN"
```

Expected: All 20 folders soft-deleted. No StackOverflowError.

- [ ] **Step 4: Test rename of deep folder (path rebuild)**

```bash
# Restore a folder first, then rename
curl -s -X PUT "http://localhost:8088/api/file/trash/$LEVEL1_ID/restore" \
  -H "Authorization: Bearer $TOKEN"

# Rename it
curl -s -X PUT "http://localhost:8088/api/file/$LEVEL1_ID/rename" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"newName":"Renamed-Root"}'

# Verify descendants have updated paths
```

- [ ] **Step 5: Concurrent operations test**

```bash
# In background: continuously upload while deleting another file
# This is a smoke test for basic concurrency handling
```

---

### Task 13: Final Report

- [ ] **Step 1: Compile test results**

Document: Pass/fail status for each test step, unexpected responses, errors.

- [ ] **Step 2: Cross-reference with static analysis findings**

For each bug found in Phase 1, note:
- Was it reproducible at runtime?
- Severity confirmation
- Recommended fix

- [ ] **Step 3: Write final report**

Save to `docs/superpowers/plans/2026-06-09-report.md` with:
1. Executive summary
2. Bug list (from Phase 1, confirmed/updated by Phase 2)
3. Test coverage table (which endpoints tested, which skipped)
4. Performance observations
5. Recommended fixes in priority order

---

## Appendix A: Pre-Identified Issues (from code review)

### P0 — Critical

| # | Issue | File | Line | Impact |
|---|---|---|---|---|
| 1 | `EsIndexServiceImpl.rebuildAll()` uses `selectByExample` instead of `selectByExampleWithBLOBs`. ES rebuild loses all `originText` (LONGTEXT field), making search useless after rebuild. | EsIndexServiceImpl.java | ~130 | Search broken after rebuild |
| 2 | `SecurityConfig` permits `/api/share/**` to all users. The `DELETE /api/share/{code}` endpoint is also under `/api/share/` so it's unprotected — anyone can delete any share link. | SecurityConfig.java | — | Security bypass |

### P1 — High

| # | Issue | File | Line | Impact |
|---|---|---|---|---|
| 3 | No `@Transactional` on any multi-step service method. If a step fails mid-operation (e.g., ES delete in `deleteFile`), DB may be inconsistent. | FileServiceImpl.java | multiple | Data inconsistency |
| 4 | `FileSystemWatcher.ensureFileInDb()` → `calculateMd5()` reads entire file into memory (`Files.readAllBytes`). Files up to 512MB will cause OOM. | FileSystemWatcher.java | ~487 | OOM crash |
| 5 | `FileServiceImpl.listTrash()` shows all users' trashed files — no `uploaderId` filter. Privacy/data leak in multi-user scenarios. | FileServiceImpl.java | ~243 | Privacy leak |
| 6 | `FileServiceImpl.deleteFile()` and `permanentDelete()` use unbounded recursion. Deep folder trees (>1000 levels) cause StackOverflowError. | FileServiceImpl.java | ~194, ~323 | Crash |

### P2 — Medium

| # | Issue | File | Line | Impact |
|---|---|---|---|---|
| 7 | `FavoriteServiceImpl.addFavorite()` doesn't verify file exists. Can favorite non-existent file IDs. | FavoriteServiceImpl.java | ~28 | Data integrity |
| 8 | `loginByCode` doesn't explicitly validate that `code` is non-null/non-blank. Null code passes to `verifyCode` which compares with stored value. | AuthController.java | ~37 | Minor validation gap |
| 9 | `FileSystemWatcher.ensureFileInDb()` hardcodes `uploaderId = 1L`. Files created by filesystem events are attributed to user 1, not the actual creator. | FileSystemWatcher.java | ~220, ~273 | Wrong attribution |
| 10 | `SearchController.search()` creates `new RestTemplate()` per request instead of reusing or injecting. | SearchController.java | ~37 | Performance |
| 11 | `FileController.upload()` doesn't handle empty `file` parameter — will NPE on `file.getOriginalFilename()`. | FileController.java | ~50 | 500 error |
| 12 | `FileServiceImpl.renameFile()` and `moveFile()` use O(n²) path rebuild via `buildPath` which walks parent chain for each descendant. | FileServiceImpl.java | ~358 | Performance |

### P3 — Low

| # | Issue | File | Line | Impact |
|---|---|---|---|---|
| 13 | `FileSystemWatcher.reconcilePending()` creates snapshot from `pendingPaths` then clears — new events between snapshot and clear are lost. | FileSystemWatcher.java | ~173 | Rare event loss |
| 14 | `OllamaService` uses `SimpleClientHttpRequestFactory` which doesn't support HTTP/2 connection pooling. | OllamaService.java | ~32 | Suboptimal |
| 15 | `EsIndexServiceImpl.scheduleStartupCleanup()` uses raw `Thread` — not managed by Spring, not cleaned up on shutdown. | EsIndexServiceImpl.java | ~41 | Resource leak |
| 16 | `FileServiceImpl.upload()` → `detectFileType()` only matches a handful of Office MIME types. Browser-uploaded MIME types may differ. | FileServiceImpl.java | ~447 | Wrong file type |
| 17 | `FileServiceImpl.getCurrentUserId()` duplicated in `FileServiceImpl`, `ShareServiceImpl`, `FavoriteServiceImpl`. Should be extracted. | multiple | — | Code duplication |

---

## Appendix B: Endpoint Test Coverage Matrix

| # | Endpoint | Method | Auth | Phase 2 Task |
|---|---|---|---|---|
| 1 | `/api/auth/send-code` | POST | Public | Task 6 |
| 2 | `/api/auth/login-by-code` | POST | Public | Task 6 |
| 3 | `/api/auth/login-by-password` | POST | Public | Task 6 |
| 4 | `/api/user/set-password` | POST | Auth | Task 6 |
| 5 | `/api/user/me` | GET | Auth | Task 6 |
| 6 | `/api/file/upload` | POST | Auth | Task 7 |
| 7 | `/api/file/create-folder` | POST | Auth | Task 7 |
| 8 | `/api/file/list` | GET | Auth | Task 7 |
| 9 | `/api/file/tree/{folderId}` | GET | Auth | Task 8 |
| 10 | `/api/file/{fileId}` | GET | Auth | Task 7 |
| 11 | `/api/file/{fileId}/download` | GET | Public | Task 7 |
| 12 | `/api/file/{fileId}/stream` | GET | Public | Task 7 |
| 13 | `/api/file/{fileId}/thumbnail` | GET | Public | Task 7 |
| 14 | `/api/file/watch` | GET | Public+token | Task 11 |
| 15 | `/api/file/{fileId}/rename` | PUT | Auth | Task 8 |
| 16 | `/api/file/{fileId}/move` | PUT | Auth | Task 8 |
| 17 | `/api/file/{fileId}` | DELETE | Auth | Task 8 |
| 18 | `/api/file/batch` | DELETE | Auth | Task 8 |
| 19 | `/api/file/trash` | GET | Auth | Task 8 |
| 20 | `/api/file/trash/{fileId}/restore` | PUT | Auth | Task 8 |
| 21 | `/api/file/trash/{fileId}` | DELETE | Auth | Task 8 |
| 22 | `/api/share/{fileId}` | POST | Auth | Task 9 |
| 23 | `/api/share/{code}` | GET | Public | Task 9 |
| 24 | `/api/share/{code}` | DELETE | Auth* | Task 9 |
| 25 | `/api/favorite/{fileId}` | POST | Auth | Task 9 |
| 26 | `/api/favorite/{fileId}` | DELETE | Auth | Task 9 |
| 27 | `/api/favorite/check/{fileId}` | GET | Auth | Task 9 |
| 28 | `/api/favorite/list` | GET | Auth | Task 9 |
| 29 | `/api/search` | GET | Auth | Task 10 |
| 30 | `/api/search/rebuild-index` | POST | Auth | Task 10 |
| 31 | Error/401 handling | — | — | Task 11 |

*Note: Endpoint 24 is incorrectly unprotected (see P0 bug #2).
