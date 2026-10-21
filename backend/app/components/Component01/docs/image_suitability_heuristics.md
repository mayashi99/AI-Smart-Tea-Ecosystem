# Minimal image suitability gate

`api/image_suitability.py` uses existing Pillow plus already-installed OpenCV
and its bundled local Haar resources. Nothing is downloaded or installed. After the existing file,
size and dimension checks, the upload endpoint assesses a thumbnail in memory
before creating temporary input files or calling the CNN, Grad-CAM++ or advisories.

Rules on an at-most-192px RGB thumbnail:

- Reject near-uniform grayscale standard deviation below 2.
- Reject extremely flat, limited-palette graphics: top eight 4-bit/channel bins
  exceed 95% of pixels and adjacent grayscale differences <=2 exceed 92%.
- Mark white, near-neutral, flat document-like inputs uncertain (white >70%,
  near-neutral >96%, flat >75%).
- Mark near-neutral graphic-like limited palettes uncertain (dominant bins >82%,
  flat >85%, near-neutral >96%). A broader palette rule falsely flagged a real
  Red Spider Mite sample, so it was narrowed; this is not independent calibration.
- Mark low-detail low-contrast inputs uncertain (standard deviation <10, flat >80%).
- Otherwise allow the existing disease pipeline, without asserting tea identity.

Version 2 additionally checks an at-most-640px RGB thumbnail for interface
geometry: at least four distinct horizontal AND vertical boundary bands, each
covering over 28% of its axis; at least one boundary on each axis covering over
50%; and over 15% near-uniform tiles in a 32-by-32 grid (RGB standard deviation
at most 6). Boundary contrast uses a maximum RGB channel difference over 24.
All these conditions must hold together. This is generic appearance evidence,
not browser recognition, OCR, filename matching, or a specific-image signature.
Metric values and the v2 method identifier are included in suitability metadata.

The real user-provided `Screenshot (2).png` was located in the local Pictures
Screenshots folder (not copied into the repository). The old live backend and
Vite proxy both returned `completed`, `grey leaf`, with the v1 method identifier:
the validation was running, but failed on this image. Its old palette share was
0.6437, flat-neighbor fraction 0.6107, white fraction 0.3549, neutral fraction
0.6052, and grayscale deviation 78.1575, so none of the v1 checks fired.
At higher resolution it has 10 horizontal and 11 vertical boundary bands,
longest boundary coverage 0.9594/0.8194, and flat-tile fraction 0.2265625.
These combined features now produce `rejected`, verified through both live
port 8015 and the same port-5173 proxy used by the frontend after restarting
only Component01. The exact screenshot's in-process API test also asserts that
the CNN/explainer and both advisory builders are never called.

No green-color requirement, filename screenshot guess, new model, dataset or new
dependency is used. Thresholds are conservative engineering heuristics, not
calibrated or independently evaluated recognition thresholds. Realistic screenshots,
photos embedded in documents, animals, buildings and other plant leaves may pass.
Some suitable photographs may be flagged. Blur and tiny leaves are not reliably
detected. Passing does NOT verify tea, disease or diagnosis. The five-class CNN
and its scientific limitations remain unchanged.

Rejected/uncertain outcomes use HTTP 200 with `analysis_status`, `message_key`,
English `message`, and heuristic metadata, with no disease/explanation/advisory
fields. Accepted results preserve old fields and add `analysis_status: completed`
and suitability metadata. Malformed files retain the existing 413/422 errors.
The UI translates the message into English/Sinhala/Tamil, clears previous image
results before selecting/analyzing, aborts superseded requests, and ignores late
responses after selection or unmount. Successful image analysis no longer writes
into the officer/forecast disease selection: image recommendations use latestImage
directly, while manual recommendation selection and officer observations remain
separate.

`api/verify_image_suitability.py --real-cnn` tests generated graphic/document
fixtures, malformed files, five real training tea samples and five actual disease
CNN/Grad-CAM++/advisory response. Artifacts use TemporaryDirectory. Generated
fixtures prove rule/control flow only; they are not real screenshot evaluation.
Use `--screenshot "<actual-local-path>"` to additionally test a real screenshot.
One screenshot and five tea samples are regression evidence, not independent
accuracy evaluation. Other real document/browser screenshots were not evaluated.
No research output is overwritten. Set TEMP/TMP to a disk with free space before
running tests or the API. Other regression scripts may write fixed report paths;
redirect their report roots to temporary storage when running them.

## Local face rejection safeguard (v3)

On an EXIF-corrected RGB thumbnail up to 1280px, use the installed OpenCV
`haarcascade_frontalface_default.xml` and `haarcascade_frontalface_alt2.xml`.
Both must detect an overlapping face (intersection over union >=0.5), using
scaleFactor 1.1, minNeighbors 8 and minimum size 40x40. Return `rejected` with
reason `HUMAN_FACE_DETECTED` before the disease pipeline. Detection is entirely
in-memory; no personal images, crops or face coordinates are saved or logged.
Missing/broken local detectors cause otherwise acceptable images to return
`uncertain` / `FACE_SAFEGUARD_UNAVAILABLE`, rather than silently bypassing the check.
Screenshot, document, size, encoding and dimension checks remain in effect.

An initial single-cascade trial with minNeighbors 6 falsely rejected a Brown
Blight sample; a diagnostic also found a Grey Leaf candidate. The final safeguard
requires stricter neighbor support and agreement of two existing cascades.
These two cascades are not independent semantic verification. No detected face
does NOT establish tea content; profiles, occlusion, small faces, animals and
other plants can pass, and false detections remain possible.

Regression inputs are the user's ORIGINAL `WIN_20250303_16_01_22_Pro.jpg` and
`WIN_20241210_06_22_42_Pro.jpg`, read in place from Camera Roll, not screenshots or
new training data. Run `--person "<original-JPEG-path>"` repeatedly to assert
rejection and zero calls to the disease/explanation and advisory builders. Real
tea inference outputs in this test are redirected to TemporaryDirectory.

Independent tea verification still needs an authorized review workflow or an
evaluated semantic verifier. Neither exists in this prototype. A fail-closed
pending-review workflow would also hold genuine tea photos until reviewed.
Implementing it requires separately approved authentication/authorization,
private storage, image-bound decisions, expiry/retention and privacy controls.
No review endpoint, officer checkbox bypass or automatic approval was added.
