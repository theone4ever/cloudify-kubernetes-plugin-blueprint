(where (service #".*connections$")
  (let [ hosts (ref #{}) ]
    (fn [e]
      (let [ key (str (:host e) "." (:service e))]
        (if (expired? e)
          (dosync (ref-set hosts (disj @hosts key)))
          (dosync (ref-set hosts (conj @hosts key)))
        )
        ;index count
        (do
        (riemann.index/update index (assoc e :host nil :metric (max 1 (count @hosts)) :service "hostcount" :ttl nil))
        )
      )
    )
  )

  (where (not (nil? (riemann.index/lookup index nil "hostcount")))
    (where (not (expired? event))
      (moving-time-window {{moving_window_size}}
        ;(combine folds/mean
        (smap folds/mean
          (fn [ev]
            (let [hostcnt (:metric (riemann.index/lookup index nil "hostcount"))
                  conns (/ (:metric ev) (max hostcnt 1))
                  cooling (not (nil? (riemann.index/lookup index "scaling" "suspended")))
                 ]
               (if (and (not cooling) (< {{scale_threshold}} conns))
                 (do
                   (process-policy-triggers ev)
                   (riemann.index/update index {:host "scaling" :service "suspended" :time (unix-time) :description "cooldown flag" :metric 0 :ttl {{cooldown_time}} :state "ok"})
                 )
               )
            )
          )
        )
      )
    )
  )
)

