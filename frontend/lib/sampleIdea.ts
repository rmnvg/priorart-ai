// Each sample is kept in sync with a pre-cached analysis in backend/.cache/,
// so it returns instantly and costs no SerpApi quota. Changing a sample's
// text without warming the cache turns its button into a live (billable,
// slow) run.
export const SAMPLE_IDEA =
  "A collapsible kayak paddle that splits into four interlocking segments, each hollow " +
  "and buoyant, so the whole paddle also serves as an emergency flotation device when " +
  "disassembled.";

// The same pipeline, described the way a farmer might dictate it — in Hindi.
export const HINDI_SAMPLE_IDEA =
  "एक सौर ऊर्जा से चलने वाला फसल सुखाने का यंत्र, जिसमें काले रंग की टिन की चादर हवा को " +
  "गर्म करती है और एक छोटा पंखा गर्म हवा को जाली वाली ट्रे के ऊपर से गुज़ारता है, ताकि " +
  "किसान टमाटर और मिर्च बिना बिजली के सुखा सकें।";
