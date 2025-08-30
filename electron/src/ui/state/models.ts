export type ID=string; export interface Suggestion{action:string;payload?:any;confidence?:number;rationale?:string}; export interface EmailSummary{thread_id:ID;summary:string;highlights:string[]};
