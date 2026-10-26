# Addendum 3 results: targeted audits

Games per cell: graders-only 4, outsiders-only 4. Confirmatory tests evaluated.

         cell          act predictor  point  lo95  hi95  observed  inside  papers
  X25-graders  co_inflated     model   0.53  0.21  0.88      0.33    True      24
  X25-graders  co_inflated  baseline   0.67  0.38  0.96      0.33   False      24
  X25-graders out_deflated     model   0.91  0.75  1.00      0.38   False      96
  X25-graders out_deflated  baseline   0.14  0.00  0.35      0.38   False      96
X25-outsiders  co_inflated     model   0.92  0.71  1.00      0.88    True      24
X25-outsiders  co_inflated  baseline   0.33  0.08  0.58      0.88   False      24
X25-outsiders out_deflated     model   0.18  0.00  0.41      0.06    True      96
X25-outsiders out_deflated  baseline   0.09  0.00  0.25      0.06    True      96

- D1 (graders-only, out_deflated): inside model PI False, inside baseline PI False: FAIL; spillover lambda 0.73 [0.31, 1.18] (0 = none, 1 = full)
- D2 (outsiders-only, co_inflated): inside model PI True, inside baseline PI False: PASS; spillover lambda 0.11 [-0.40, 0.67] (0 = none, 1 = full)
- H9 outsider deflation, graders-only minus outsiders-only: +0.31, exact permutation p = 0.171 (minimum possible 0.029)
- H9b co-grader inflation, outsiders-only minus graders-only: +0.54, exact permutation p = 0.029
- H10 endgame (outsiders-only): outsider deflation round 4 minus rounds 2-3 +0.00, 1 games up / 1 down of 4, exact sign-flip p = 1.000
- H10 endgame (graders-only): outsider deflation round 4 minus rounds 2-3 +0.19, 2 games up / 1 down of 4, exact sign-flip p = 0.750
- In-group advantage, graders-only (0.5 expected re-marked papers per round): +2.58 over 12 rounds (uniform 5/10/20%: 0.3/0.6/1.2 papers, +3.0/+1.9/+1.0)
- In-group advantage, outsiders-only (1.0 expected re-marked papers per round): +3.04 over 12 rounds (uniform 5/10/20%: 0.3/0.6/1.2 papers, +3.0/+1.9/+1.0)
