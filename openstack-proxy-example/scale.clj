; Kubernetes scaling policy - makes assumption that make it appropriate
; only for demo purposes

(where (service "blorf")
  (by :host
    (moving-time-window window-size
      ; combine floating window and inject new event
      (combine folds/mean
         (with :service "avg" reinject)
      )
    )
  )
)

(where (service "avg")
  (coalesce
      (combine folds/mean
        ; combine windows into global average. only scale if not suspended (cooldown)
        (where (and (> metric metric-threshold) (not (riemann.index/lookup index "scaling" "suspended")))
           ;set suspended flag
           #(info "SCALE TRIGGER" %)
           (process-policy-triggers)
           (fn [ev] (riemann.index/update index (event {:host "scaling" :service "suspended" :ttl cooldown-time})))
        )
      )
  )
)

