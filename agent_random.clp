(defmodule MAIN (export ?ALL))

    (deftemplate percept
      (slot x) (slot y)
      (slot steps)      
      (slot breeze)
      (slot stench)
      (slot glitter)
      (slot energy)
    )

    (deftemplate counter
      (slot step)
    )
   
   (deftemplate action
      (slot move)
   )



   (deffacts initial
     (counter (step 0))
   )
   
 
 (defrule deliberate
   (counter (step ?step))
  =>
  (focus RANDOM)
 )
   
   
(defmodule RANDOM (import MAIN ?ALL))



  (deffacts moves
    (actions right up left down);; quit grab pit-north pit-south pit-west pit-east)
  )

  (defrule pick-one-randomly
    (counter (step ?step))
    (actions $?acts)
    =>
    (bind ?r (random 1 (length$ $?acts)))
    (assert (action (move  (nth$ ?r $?acts))))
    (printout t "action: " (nth$ ?r $?acts) crlf)
  )
     
