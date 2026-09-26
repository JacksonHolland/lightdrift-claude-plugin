// Plain Sanity schema definitions; no server code or credentials imported here.
const stored = (name, type = 'string') => ({name, type, readOnly: true})
export const imageReviewCandidate = {
  name: 'imageReviewCandidate', type: 'object', title: 'Image candidate',
  fields: [
    stored('assetId'), stored('source'), stored('provenance'), stored('attribution', 'text'),
    stored('rightsJson', 'text'), stored('candidateJson', 'text'),
    {name: 'decision', type: 'string', initialValue: 'pending', options: {list: ['pending', 'hold', 'rejected', 'approved']},
      validation: Rule => Rule.required()},
    {name: 'reviewer', type: 'string'}, {name: 'reviewedAt', type: 'datetime'},
    {name: 'reviewNotes', type: 'text', description: 'Intended use, source/license checks, required credit and unresolved restrictions'},
  ],
  validation: Rule => Rule.custom(candidate => {
    if (candidate?.decision !== 'approved') return true
    return candidate.reviewer?.trim() && candidate.reviewNotes?.trim() && candidate.reviewedAt
      ? true : 'Approval requires reviewer, timestamp and intended-use review notes'
  }),
  preview: {select: {title: 'assetId', subtitle: 'decision'}},
}
export const imageReview = {
  name: 'imageReview', type: 'document', title: 'Image review queue',
  fields: [stored('title'), stored('contentDraftId'), stored('queryId'), stored('query', 'text'),
    stored('isFixture', 'boolean'), stored('responseJson', 'text'),
    {name: 'candidates', type: 'array', of: [{type: 'imageReviewCandidate'}]}],
}
// Queue records are for editorial review, not publication. This UI guard is not API authorization.
export function reviewActions(previous, context) {
  return context.schemaType === 'imageReview' ? previous.filter(action => action.action === 'delete') : previous
}
export default [imageReviewCandidate, imageReview]
