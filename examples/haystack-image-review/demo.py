import json
from pathlib import Path
from haystack import Pipeline
from lightdrift_haystack import LightdriftImageReview

pipeline = Pipeline()
pipeline.add_component('images', LightdriftImageReview())
fixture = json.loads((Path(__file__).parent / 'fixtures/candidates.json').read_text())
print(json.dumps(pipeline.run({'images': {'visual_brief': 'A quiet coastal trail',
                                        'candidate_count': 2, 'fixture': fixture}}), indent=2))
