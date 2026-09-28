# Test cases

This section sheds light on the test cases that are setup for SEICHE. For a general and methodological description of the test cases, [see the technical report](https://gitlab.com/garinto/technical-report-2023-2026/-/blob/main/main.pdf). 

## Full test cases

- Marmande: FR, Telemac2D, agricultural damages
- St-Omer: FR, FloodML, urban damages 
- Chinon: FR, SWOT, agricultural damages
- Ohio: USA, ...

## Light test cases

Some test data however, is shipped directly with the repo. It serves mainly as a full regression test when `test_full_pipeline` is called: `test_full_pipeline_data.yml` holds cryptographic SHA256 signatures of all the input and output files of the pipeline for both St-Omer 'light' and Marmande 'light', to prevent any breaking change from occuring. These "light" versions were obtained in two ways:
  - For St-Omer, every file from the full test case was cropped on a very small circle of a few hundred meters in radius. So the behaviour stays the same, only it happens on a much smaller extent.
  - For Marmande, we couldn't cut the output .slf files. Instead, only half a dozen or so of timesteps were kept, uniformly sampled on the 2019 event, greatly decreasing the size and computation time, at the cost of precision; but the spatial extent is the same as in the full test case.
