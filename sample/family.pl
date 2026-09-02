
man(serhii).
man(vova).
man(senya).
man(vasya).

woman(ira).
woman(tanya).
woman(galya).
woman(lyuda).

parent_child(senya, vova).
parent_child(galya, vova).
parent_child(senya, lyuda).
parent_child(galya, lyuda).
parent_child(vova, serhii).
parent_child(vova, ira).
parent_child(tanya, serhii).
parent_child(tanya, ira).


aunt(Aunt, Nephew) :-
	woman(Aunt),
	siblings(Aunt, Sibling),
	parent_child(Sibling, Nephew).


siblings(SibA, SibB) :-
	parent_child(Father, SibA),
	parent_child(Father, SibB),
	parent_child(Mother, SibA),
	parent_child(Mother, SibB),
	man(Father),
	woman(Mother),
	SibA != SibB.


% Visualiazation of how `aunt(lyuda, Nephew)` works:

aunt(lyuda, Nephew),
    woman(lyuda),
	siblings(lyuda, Sibling),
		parent_child(Father, lyuda),
		parent_child(Father, Sibling),
		parent_child(Mother, lyuda),
		parent_child(Mother, Sibling),
		man(Father),
		woman(Mother),
		lyuda != Sibling,
	parent_child(Sibling, Nephew).


% Advanced SQL

order_invalid_ticket(Order, Ticket) :-
	order(Order),
	ticket(Ticket),
	Ticket.order_id = Order.id,
	invalid_ticket(Ticket).


invalid_ticket(Ticket) :-
	ticket(Ticket),
	code(Code),
	Ticket.code_id = Code.id,
	Code.invalidated = true.
