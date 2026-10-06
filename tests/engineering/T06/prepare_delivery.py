"""Generate a reviewable integration patch; never mutate shared production files."""
import difflib
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3]
HERE=Path(__file__).resolve().parent
def canonical_source(old):
    new=old.replace('bytes.length>1_048_576','bytes.length>8*1_048_576')
    old_config='.enable(DeserializationFeature.FAIL_ON_TRAILING_TOKENS);'
    new_config='''.enable(DeserializationFeature.FAIL_ON_TRAILING_TOKENS)
            .disable(com.fasterxml.jackson.core.json.JsonWriteFeature.WRITE_HEX_UPPER_CASE.mappedFeature())
            .enable(com.fasterxml.jackson.core.json.JsonWriteFeature.COMBINE_UNICODE_SURROGATES_IN_UTF8.mappedFeature());'''
    assert old_config in new
    return new.replace(old_config,new_config)

if __name__=='__main__':
    changes=[]
    path='backend/src/main/java/com/example/editorial/shared/CanonicalRequest.java'
    old=(ROOT/path).read_text(encoding='utf-8');new=canonical_source(old)
    changes.append((path,old,new))
    path='backend/src/main/java/com/example/editorial/bootstrap/ArticleIntegration.java'
    assert not (ROOT/path).exists()
    changes.append((path,'',(HERE/'ArticleIntegration.java').read_text(encoding='utf-8')))
    patch=''
    for path,old,new in changes:
        patch+='diff --git a/'+path+' b/'+path+'\n'
        if not old:patch+='new file mode 100644\n'
        patch+=''.join(difflib.unified_diff(old.splitlines(True),new.splitlines(True),fromfile='a/'+path if old else '/dev/null',tofile='b/'+path))
    (HERE/'shared-integration.patch').write_text(patch,encoding='utf-8',newline='\n')
    print('Wrote proposed canonical-v1 UTF8/control escaping + envelope limit + composition root patch.')
