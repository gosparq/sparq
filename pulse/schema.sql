--
-- PostgreSQL database dump
--

\restrict cNtJfufvi0V9IpOEadAonmpgqfCf0TkgnrTlwaTB5aef7Eoh2qVoOhIL3WSExp3

-- Dumped from database version 17.9 (Debian 17.9-1.pgdg13+1)
-- Dumped by pg_dump version 17.9 (Debian 17.9-1.pgdg13+1)

SET statement_timeout = 0;
SET lock_timeout = 0;
SET idle_in_transaction_session_timeout = 0;
SET transaction_timeout = 0;
SET client_encoding = 'UTF8';
SET standard_conforming_strings = on;
SELECT pg_catalog.set_config('search_path', '', false);
SET check_function_bodies = false;
SET xmloption = content;
SET client_min_messages = warning;
SET row_security = off;

--
-- Name: SCHEMA public; Type: COMMENT; Schema: -; Owner: -
--

COMMENT ON SCHEMA public IS '';


--
-- Name: accounttype; Type: TYPE; Schema: public; Owner: -
--

CREATE TYPE public.accounttype AS ENUM (
    'ASSET',
    'LIABILITY',
    'EQUITY',
    'REVENUE',
    'EXPENSE'
);


--
-- Name: activitytype; Type: TYPE; Schema: public; Owner: -
--

CREATE TYPE public.activitytype AS ENUM (
    'STATUS_CHANGE',
    'NOTE_ADDED',
    'INTERVIEW_SCHEDULED',
    'INTERVIEW_COMPLETED',
    'EMAIL_SENT',
    'RESUME_VIEWED',
    'RATING_CHANGED',
    'CREATED'
);


--
-- Name: applicationstatus; Type: TYPE; Schema: public; Owner: -
--

CREATE TYPE public.applicationstatus AS ENUM (
    'NEW',
    'SCREENING',
    'INTERVIEWING',
    'OFFER',
    'HIRED',
    'REJECTED',
    'WITHDRAWN'
);


--
-- Name: candidatesource; Type: TYPE; Schema: public; Owner: -
--

CREATE TYPE public.candidatesource AS ENUM (
    'WEBSITE',
    'LINKEDIN',
    'INDEED',
    'REFERRAL',
    'AGENCY',
    'OTHER'
);


--
-- Name: contactsource; Type: TYPE; Schema: public; Owner: -
--

CREATE TYPE public.contactsource AS ENUM (
    'WEBSITE',
    'REFERRAL',
    'PHONE',
    'SOCIAL',
    'OTHER'
);


--
-- Name: contacttype; Type: TYPE; Schema: public; Owner: -
--

CREATE TYPE public.contacttype AS ENUM (
    'PROSPECT',
    'CUSTOMER',
    'VENDOR',
    'OTHER'
);


--
-- Name: employeestatus; Type: TYPE; Schema: public; Owner: -
--

CREATE TYPE public.employeestatus AS ENUM (
    'ACTIVE',
    'ON_LEAVE',
    'TERMINATED',
    'CONTRACTOR',
    'INACTIVE'
);


--
-- Name: employeetype; Type: TYPE; Schema: public; Owner: -
--

CREATE TYPE public.employeetype AS ENUM (
    'FULL_TIME',
    'PART_TIME',
    'CONTRACTOR',
    'INTERN'
);


--
-- Name: expensecategory; Type: TYPE; Schema: public; Owner: -
--

CREATE TYPE public.expensecategory AS ENUM (
    'MATERIALS',
    'FUEL',
    'TOOLS',
    'SUBCONTRACTOR',
    'PERMITS',
    'SUPPLIES',
    'SOFTWARE',
    'MEALS',
    'TRAVEL',
    'PROFESSIONAL',
    'INSURANCE',
    'UTILITIES',
    'MARKETING',
    'RENT',
    'TRAINING',
    'OTHER'
);


--
-- Name: expensestatus; Type: TYPE; Schema: public; Owner: -
--

CREATE TYPE public.expensestatus AS ENUM (
    'PENDING',
    'APPROVED',
    'REJECTED'
);


--
-- Name: industry; Type: TYPE; Schema: public; Owner: -
--

CREATE TYPE public.industry AS ENUM (
    'FIELD_SERVICE',
    'PROFESSIONAL_SERVICES',
    'WORKFORCE'
);


--
-- Name: interactiontype; Type: TYPE; Schema: public; Owner: -
--

CREATE TYPE public.interactiontype AS ENUM (
    'READ',
    'REACTION',
    'BOOKMARK',
    'THREAD_READ',
    'PIN',
    'LIKE',
    'EDIT',
    'DELETE',
    'ACKNOWLEDGED'
);


--
-- Name: interviewrecommendation; Type: TYPE; Schema: public; Owner: -
--

CREATE TYPE public.interviewrecommendation AS ENUM (
    'STRONG_HIRE',
    'HIRE',
    'MAYBE',
    'NO_HIRE',
    'STRONG_NO_HIRE'
);


--
-- Name: interviewstatus; Type: TYPE; Schema: public; Owner: -
--

CREATE TYPE public.interviewstatus AS ENUM (
    'SCHEDULED',
    'COMPLETED',
    'CANCELLED',
    'NO_SHOW'
);


--
-- Name: interviewtype; Type: TYPE; Schema: public; Owner: -
--

CREATE TYPE public.interviewtype AS ENUM (
    'PHONE_SCREEN',
    'VIDEO',
    'ONSITE',
    'TECHNICAL',
    'PANEL'
);


--
-- Name: invitestatus; Type: TYPE; Schema: public; Owner: -
--

CREATE TYPE public.invitestatus AS ENUM (
    'PENDING',
    'ACCEPTED',
    'CANCELLED'
);


--
-- Name: jobstatus; Type: TYPE; Schema: public; Owner: -
--

CREATE TYPE public.jobstatus AS ENUM (
    'DRAFT',
    'OPEN',
    'ON_HOLD',
    'CLOSED'
);


--
-- Name: jobtype; Type: TYPE; Schema: public; Owner: -
--

CREATE TYPE public.jobtype AS ENUM (
    'FULL_TIME',
    'PART_TIME',
    'CONTRACT',
    'INTERNSHIP'
);


--
-- Name: leaverequeststatus; Type: TYPE; Schema: public; Owner: -
--

CREATE TYPE public.leaverequeststatus AS ENUM (
    'DRAFT',
    'PENDING',
    'APPROVED',
    'DENIED',
    'CANCELLED'
);


--
-- Name: leavetype; Type: TYPE; Schema: public; Owner: -
--

CREATE TYPE public.leavetype AS ENUM (
    'VACATION',
    'SICK',
    'PERSONAL',
    'BEREAVEMENT',
    'JURY_DUTY',
    'OTHER'
);


--
-- Name: onboardingstatus; Type: TYPE; Schema: public; Owner: -
--

CREATE TYPE public.onboardingstatus AS ENUM (
    'DRAFT',
    'SENT',
    'IN_PROGRESS',
    'PENDING_REVIEW',
    'COMPLETED',
    'CANCELLED'
);


--
-- Name: onboardingtype; Type: TYPE; Schema: public; Owner: -
--

CREATE TYPE public.onboardingtype AS ENUM (
    'W2',
    'CONTRACTOR'
);


--
-- Name: paidby; Type: TYPE; Schema: public; Owner: -
--

CREATE TYPE public.paidby AS ENUM (
    'COMPANY',
    'PERSONAL'
);


--
-- Name: punchcorrectionrequeststatus; Type: TYPE; Schema: public; Owner: -
--

CREATE TYPE public.punchcorrectionrequeststatus AS ENUM (
    'PENDING',
    'APPROVED',
    'DENIED'
);


--
-- Name: punchtype; Type: TYPE; Schema: public; Owner: -
--

CREATE TYPE public.punchtype AS ENUM (
    'IN',
    'OUT'
);


--
-- Name: reimbursementstatus; Type: TYPE; Schema: public; Owner: -
--

CREATE TYPE public.reimbursementstatus AS ENUM (
    'NOT_APPLICABLE',
    'PENDING',
    'REIMBURSED',
    'WAIVED'
);


--
-- Name: salarytype; Type: TYPE; Schema: public; Owner: -
--

CREATE TYPE public.salarytype AS ENUM (
    'HOURLY',
    'YEARLY'
);


--
-- Name: taskassignee; Type: TYPE; Schema: public; Owner: -
--

CREATE TYPE public.taskassignee AS ENUM (
    'EMPLOYEE',
    'ADMIN'
);


--
-- Name: taskstatus; Type: TYPE; Schema: public; Owner: -
--

CREATE TYPE public.taskstatus AS ENUM (
    'PENDING',
    'COMPLETED',
    'SKIPPED'
);


--
-- Name: terminationreason; Type: TYPE; Schema: public; Owner: -
--

CREATE TYPE public.terminationreason AS ENUM (
    'RESIGNATION',
    'LAYOFF',
    'TERMINATION_FOR_CAUSE',
    'RETIREMENT',
    'CONTRACT_END',
    'MUTUAL_AGREEMENT',
    'OTHER'
);


--
-- Name: timeentrystatus; Type: TYPE; Schema: public; Owner: -
--

CREATE TYPE public.timeentrystatus AS ENUM (
    'SUBMITTED',
    'APPROVED',
    'REJECTED',
    'INVOICED'
);


SET default_tablespace = '';

SET default_table_access_method = heap;

--
-- Name: accounting_account; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.accounting_account (
    id integer NOT NULL,
    code character varying(20) NOT NULL,
    name character varying(100) NOT NULL,
    account_type public.accounttype NOT NULL,
    parent_id integer,
    is_active boolean,
    description character varying(255),
    tax_category character varying(100),
    created_at timestamp without time zone,
    teamspace_id uuid,
    organization_id uuid NOT NULL
);


--
-- Name: accounting_account_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.accounting_account_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: accounting_account_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.accounting_account_id_seq OWNED BY public.accounting_account.id;


--
-- Name: accounting_ledger; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.accounting_ledger (
    id integer NOT NULL,
    entry_date date NOT NULL,
    account_id integer NOT NULL,
    description character varying(255) NOT NULL,
    debit numeric(10,2),
    credit numeric(10,2),
    reference_type character varying(50),
    reference_id integer,
    fiscal_year integer NOT NULL,
    fiscal_period integer NOT NULL,
    vendor_name character varying(100),
    created_at timestamp without time zone,
    created_by_id integer,
    teamspace_id uuid,
    organization_id uuid NOT NULL
);


--
-- Name: accounting_ledger_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.accounting_ledger_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: accounting_ledger_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.accounting_ledger_id_seq OWNED BY public.accounting_ledger.id;


--
-- Name: action_item; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.action_item (
    id integer NOT NULL,
    title character varying(200) NOT NULL,
    urgency_tier integer DEFAULT 2 NOT NULL,
    assignee_id integer,
    raised_by_id integer,
    context_note character varying(500),
    source_type character varying(50),
    source_id integer,
    status character varying(20) DEFAULT 'open'::character varying NOT NULL,
    resolution_note character varying(1024),
    broadcast_group_id uuid,
    snoozed boolean DEFAULT false NOT NULL,
    snooze_until timestamp without time zone,
    resolved_at timestamp without time zone,
    resolved_by_id integer,
    created_at timestamp without time zone DEFAULT now() NOT NULL,
    updated_at timestamp without time zone DEFAULT now() NOT NULL,
    teamspace_id uuid,
    area_id integer,
    project_id integer,
    due_date date,
    workflow_status character varying(30) DEFAULT 'todo'::character varying NOT NULL,
    is_blocker boolean DEFAULT false NOT NULL,
    organization_id uuid NOT NULL
);


--
-- Name: action_item_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.action_item_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: action_item_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.action_item_id_seq OWNED BY public.action_item.id;


--
-- Name: action_item_log; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.action_item_log (
    id integer NOT NULL,
    action_item_id integer NOT NULL,
    event_type character varying(30) NOT NULL,
    actor_id integer,
    detail character varying(500),
    created_at timestamp without time zone DEFAULT now() NOT NULL
);


--
-- Name: action_item_log_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.action_item_log_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: action_item_log_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.action_item_log_id_seq OWNED BY public.action_item_log.id;


--
-- Name: action_item_watcher; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.action_item_watcher (
    action_item_id integer NOT NULL,
    watcher_id integer NOT NULL
);


--
-- Name: activity_log; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.activity_log (
    id integer NOT NULL,
    member_id integer,
    action character varying(50) NOT NULL,
    model_type character varying(50) NOT NULL,
    record_id integer,
    title character varying(100) NOT NULL,
    description character varying(255) NOT NULL,
    icon character varying(50),
    color character varying(20),
    url character varying(255),
    created_at timestamp without time zone NOT NULL,
    teamspace_id uuid,
    organization_id uuid NOT NULL
);


--
-- Name: activity_log_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.activity_log_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: activity_log_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.activity_log_id_seq OWNED BY public.activity_log.id;


--
-- Name: ai_pending_action; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.ai_pending_action (
    id integer NOT NULL,
    channel_id integer NOT NULL,
    trigger_chat_id integer,
    proposal_chat_id integer,
    created_by_id integer NOT NULL,
    tool_name character varying(100) NOT NULL,
    args_json json NOT NULL,
    status character varying(20) NOT NULL,
    clarification_json json,
    result_json json,
    error text,
    created_at timestamp without time zone,
    updated_at timestamp without time zone,
    teamspace_id uuid,
    organization_id uuid NOT NULL
);


--
-- Name: ai_pending_action_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.ai_pending_action_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: ai_pending_action_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.ai_pending_action_id_seq OWNED BY public.ai_pending_action.id;


--
-- Name: alembic_version; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.alembic_version (
    version_num character varying(32) NOT NULL
);


--
-- Name: application; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.application (
    id integer NOT NULL,
    created_at timestamp without time zone,
    updated_at timestamp without time zone,
    job_posting_id integer NOT NULL,
    candidate_id integer NOT NULL,
    status public.applicationstatus,
    applied_at timestamp without time zone,
    cover_letter text,
    rejection_reason character varying(200),
    hired_at timestamp without time zone,
    rating integer,
    onboarding_record_id integer,
    teamspace_id uuid,
    created_by_id integer,
    updated_by_id integer,
    organization_id uuid NOT NULL
);


--
-- Name: application_activity; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.application_activity (
    id integer NOT NULL,
    application_id integer NOT NULL,
    activity_type public.activitytype NOT NULL,
    description character varying(500),
    old_value character varying(200),
    new_value character varying(200),
    created_at timestamp without time zone,
    created_by_id integer,
    teamspace_id uuid,
    organization_id uuid NOT NULL
);


--
-- Name: application_activity_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.application_activity_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: application_activity_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.application_activity_id_seq OWNED BY public.application_activity.id;


--
-- Name: application_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.application_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: application_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.application_id_seq OWNED BY public.application.id;


--
-- Name: attachment; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.attachment (
    id integer NOT NULL,
    uuid character varying(36) NOT NULL,
    filename character varying(255) NOT NULL,
    mime_type character varying(100),
    size_bytes integer,
    created_at timestamp without time zone,
    teamspace_id uuid,
    organization_id uuid NOT NULL
);


--
-- Name: attachment_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.attachment_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: attachment_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.attachment_id_seq OWNED BY public.attachment.id;


--
-- Name: attachment_link; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.attachment_link (
    id integer NOT NULL,
    attachment_id integer NOT NULL,
    entity_type character varying(50) NOT NULL,
    entity_id integer NOT NULL,
    created_at timestamp without time zone,
    teamspace_id uuid,
    organization_id uuid NOT NULL
);


--
-- Name: attachment_link_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.attachment_link_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: attachment_link_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.attachment_link_id_seq OWNED BY public.attachment_link.id;


--
-- Name: audit_log; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.audit_log (
    id integer NOT NULL,
    organization_id uuid NOT NULL,
    actor_user_id integer,
    actor_organization_user_id integer,
    action character varying(100) NOT NULL,
    target_type character varying(50) NOT NULL,
    target_id character varying(100),
    teamspace_id uuid,
    metadata_json jsonb,
    created_at timestamp without time zone DEFAULT now() NOT NULL
);


--
-- Name: audit_log_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.audit_log_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: audit_log_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.audit_log_id_seq OWNED BY public.audit_log.id;


--
-- Name: auth_settings; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.auth_settings (
    id integer NOT NULL,
    local_auth_enabled boolean,
    magic_link_enabled boolean,
    sms_enabled boolean,
    google_enabled boolean,
    google_client_id character varying(255),
    google_client_secret text,
    google_drive_enabled boolean,
    microsoft_enabled boolean,
    microsoft_client_id character varying(255),
    microsoft_client_secret text,
    github_enabled boolean,
    github_client_id character varying(255),
    github_client_secret text,
    linkedin_enabled boolean,
    linkedin_client_id character varying(255),
    linkedin_client_secret text,
    updated_at timestamp without time zone,
    teamspace_id uuid,
    organization_id uuid NOT NULL
);


--
-- Name: auth_settings_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.auth_settings_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: auth_settings_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.auth_settings_id_seq OWNED BY public.auth_settings.id;


--
-- Name: billing_plan; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.billing_plan (
    id uuid NOT NULL,
    code character varying(50) NOT NULL,
    display_name character varying(100) NOT NULL,
    price_cents integer NOT NULL,
    annual_price_cents integer NOT NULL,
    stripe_price_id character varying(255),
    stripe_annual_price_id character varying(255),
    features json NOT NULL,
    status character varying(20) NOT NULL,
    created_at timestamp without time zone,
    updated_at timestamp without time zone
);


--
-- Name: billing_subscription; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.billing_subscription (
    id uuid NOT NULL,
    organization_id uuid NOT NULL,
    plan_id uuid NOT NULL,
    state character varying(20) NOT NULL,
    current_period_start timestamp without time zone,
    current_period_end timestamp without time zone,
    cancel_at_period_end boolean NOT NULL,
    stripe_subscription_id character varying(255),
    created_at timestamp without time zone,
    updated_at timestamp without time zone
);


--
-- Name: candidate; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.candidate (
    id integer NOT NULL,
    created_at timestamp without time zone,
    updated_at timestamp without time zone,
    first_name character varying(100) NOT NULL,
    last_name character varying(100) NOT NULL,
    email character varying(255) NOT NULL,
    phone character varying(50),
    city character varying(100),
    state character varying(100),
    country character varying(100),
    current_company character varying(200),
    current_title character varying(200),
    linkedin_url character varying(500),
    resume_id integer,
    source public.candidatesource,
    source_detail character varying(200),
    tags character varying(500),
    notes text,
    teamspace_id uuid,
    created_by_id integer,
    updated_by_id integer,
    organization_id uuid NOT NULL
);


--
-- Name: candidate_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.candidate_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: candidate_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.candidate_id_seq OWNED BY public.candidate.id;


--
-- Name: canned_action; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.canned_action (
    id integer NOT NULL,
    teamspace_id uuid,
    title character varying(200) NOT NULL,
    default_tier integer,
    sort_order integer DEFAULT 0 NOT NULL,
    created_by_id integer,
    created_at timestamp without time zone DEFAULT now() NOT NULL,
    organization_id uuid NOT NULL
);


--
-- Name: canned_action_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.canned_action_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: canned_action_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.canned_action_id_seq OWNED BY public.canned_action.id;


--
-- Name: update_channel; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.update_channel (
    id integer NOT NULL,
    name character varying(50) NOT NULL,
    description character varying(200),
    created_at timestamp without time zone,
    created_by_id integer,
    is_private boolean,
    teamspace_id uuid,
    require_ten_four boolean DEFAULT false,
    project_id integer,
    organization_id uuid NOT NULL,
    is_default boolean
);


--
-- Name: channel_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.channel_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: channel_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.channel_id_seq OWNED BY public.update_channel.id;


--
-- Name: clock_punch; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.clock_punch (
    id integer NOT NULL,
    member_id integer NOT NULL,
    punch_type public.punchtype NOT NULL,
    punch_time timestamp without time zone NOT NULL,
    time_entry_id integer,
    source character varying(50),
    ip_address character varying(45),
    created_at timestamp without time zone,
    latitude double precision,
    longitude double precision,
    location_accuracy double precision,
    outside_geofence boolean,
    needs_review boolean,
    location_address character varying(500),
    teamspace_id uuid,
    organization_id uuid NOT NULL
);


--
-- Name: clock_punch_adjustment; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.clock_punch_adjustment (
    id integer NOT NULL,
    clock_punch_id integer NOT NULL,
    adjusted_by_id integer NOT NULL,
    original_punch_time timestamp without time zone NOT NULL,
    new_punch_time timestamp without time zone NOT NULL,
    reason text,
    created_at timestamp without time zone,
    teamspace_id uuid,
    organization_id uuid NOT NULL
);


--
-- Name: clock_punch_adjustment_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.clock_punch_adjustment_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: clock_punch_adjustment_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.clock_punch_adjustment_id_seq OWNED BY public.clock_punch_adjustment.id;


--
-- Name: clock_punch_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.clock_punch_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: clock_punch_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.clock_punch_id_seq OWNED BY public.clock_punch.id;


--
-- Name: event; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.event (
    id integer NOT NULL,
    title character varying(255) NOT NULL,
    description text,
    scheduled_date date NOT NULL,
    scheduled_start_time time without time zone,
    scheduled_end_time time without time zone,
    is_all_day boolean,
    location character varying(255),
    created_at timestamp without time zone,
    updated_at timestamp without time zone,
    teamspace_id uuid,
    created_by_id integer,
    updated_by_id integer,
    organization_id uuid NOT NULL
);


--
-- Name: company_event_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.company_event_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: company_event_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.company_event_id_seq OWNED BY public.event.id;


--
-- Name: update_nudge_log; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.update_nudge_log (
    id integer NOT NULL,
    teamspace_id uuid,
    template_id integer NOT NULL,
    user_id integer NOT NULL,
    nudged_at timestamp without time zone NOT NULL,
    nudge_type character varying(20),
    suggested_value character varying(20),
    responded_at timestamp without time zone,
    response_value character varying(20),
    dismissed boolean DEFAULT false NOT NULL,
    organization_id uuid NOT NULL
);


--
-- Name: connect_nudge_log_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.connect_nudge_log_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: connect_nudge_log_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.connect_nudge_log_id_seq OWNED BY public.update_nudge_log.id;


--
-- Name: update_post; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.update_post (
    id integer NOT NULL,
    template_id integer,
    post_type character varying(50) NOT NULL,
    member_id integer,
    payload json NOT NULL,
    visibility character varying(20) NOT NULL,
    is_anonymous boolean NOT NULL,
    created_at timestamp without time zone NOT NULL,
    teamspace_id uuid,
    expires_at timestamp without time zone,
    area_id integer,
    channel_id integer,
    is_win boolean DEFAULT false NOT NULL,
    parent_id integer,
    subject character varying(300),
    title character varying(255),
    migrated_from character varying(50),
    reply_count integer DEFAULT 0 NOT NULL,
    last_reply_at timestamp without time zone,
    last_reply_member_id integer,
    pinned boolean DEFAULT false NOT NULL,
    mentioned_member_ids json,
    target_user_id integer,
    organization_id uuid NOT NULL
);


--
-- Name: connect_post_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.connect_post_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: connect_post_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.connect_post_id_seq OWNED BY public.update_post.id;


--
-- Name: update_post_reaction; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.update_post_reaction (
    id integer NOT NULL,
    post_id integer NOT NULL,
    member_id integer NOT NULL,
    emoji character varying(10) NOT NULL,
    created_at timestamp without time zone,
    teamspace_id uuid,
    organization_id uuid NOT NULL
);


--
-- Name: connect_post_reaction_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.connect_post_reaction_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: connect_post_reaction_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.connect_post_reaction_id_seq OWNED BY public.update_post_reaction.id;


--
-- Name: update_template; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.update_template (
    id integer NOT NULL,
    teamspace_id uuid,
    post_type character varying(50) NOT NULL,
    name character varying(100) NOT NULL,
    description character varying(255),
    fields json NOT NULL,
    anonymous boolean,
    nudge_enabled boolean,
    nudge_time character varying(5),
    is_active boolean,
    sort_order integer,
    created_at timestamp without time zone,
    updated_at timestamp without time zone,
    schedule_type character varying(10),
    interval_minutes integer,
    grace_minutes integer DEFAULT 30,
    nudge_scope json
);


--
-- Name: connect_template_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.connect_template_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: connect_template_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.connect_template_id_seq OWNED BY public.update_template.id;


--
-- Name: contact; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.contact (
    id integer NOT NULL,
    first_name character varying(100),
    last_name character varying(100),
    email character varying(255),
    phone character varying(50),
    is_company boolean,
    company_name character varying(255),
    contact_type public.contacttype NOT NULL,
    source public.contactsource,
    billing_address character varying(255),
    billing_address_2 character varying(255),
    city character varying(100),
    state character varying(100),
    zip_code character varying(20),
    country character varying(100),
    payment_terms integer,
    tax_exempt boolean,
    notes text,
    portal_access_token character varying(64),
    created_at timestamp without time zone,
    updated_at timestamp without time zone,
    converted_to_customer_at timestamp without time zone,
    teamspace_id uuid,
    created_by_id integer,
    updated_by_id integer,
    deleted_at timestamp without time zone,
    deleted_by_id integer,
    organization_id uuid NOT NULL
);


--
-- Name: contact_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.contact_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: contact_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.contact_id_seq OWNED BY public.contact.id;


--
-- Name: update_follow; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.update_follow (
    id integer NOT NULL,
    entity_type character varying(50) NOT NULL,
    entity_id integer NOT NULL,
    member_id integer NOT NULL,
    created_at timestamp without time zone DEFAULT now(),
    teamspace_id uuid,
    organization_id uuid NOT NULL
);


--
-- Name: content_follow_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.content_follow_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: content_follow_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.content_follow_id_seq OWNED BY public.update_follow.id;


--
-- Name: device_token; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.device_token (
    id integer NOT NULL,
    user_id integer NOT NULL,
    device_token character varying(512) NOT NULL,
    platform character varying(20) NOT NULL,
    device_id character varying(255) NOT NULL,
    created_at timestamp without time zone NOT NULL,
    updated_at timestamp without time zone NOT NULL
);


--
-- Name: device_token_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.device_token_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: device_token_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.device_token_id_seq OWNED BY public.device_token.id;


--
-- Name: dm; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.dm (
    id integer NOT NULL,
    thread_id integer NOT NULL,
    member_id integer,
    content text NOT NULL,
    created_at timestamp without time zone,
    read_at timestamp without time zone,
    mentioned_member_ids json,
    webhook_id integer,
    webhook_username character varying(80),
    organization_id uuid NOT NULL
);


--
-- Name: direct_message_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.direct_message_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: direct_message_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.direct_message_id_seq OWNED BY public.dm.id;


--
-- Name: dm_ack; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.dm_ack (
    id integer NOT NULL,
    message_id integer NOT NULL,
    member_id integer NOT NULL,
    created_at timestamp without time zone,
    teamspace_id uuid,
    organization_id uuid NOT NULL
);


--
-- Name: dm_acknowledgment_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.dm_acknowledgment_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: dm_acknowledgment_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.dm_acknowledgment_id_seq OWNED BY public.dm_ack.id;


--
-- Name: dm_reaction; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.dm_reaction (
    id integer NOT NULL,
    message_id integer NOT NULL,
    member_id integer NOT NULL,
    emoji character varying(10) NOT NULL,
    created_at timestamp without time zone,
    organization_id uuid NOT NULL
);


--
-- Name: dm_reaction_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.dm_reaction_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: dm_reaction_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.dm_reaction_id_seq OWNED BY public.dm_reaction.id;


--
-- Name: dm_thread; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.dm_thread (
    id integer NOT NULL,
    member1_id integer NOT NULL,
    member2_id integer NOT NULL,
    created_at timestamp without time zone,
    updated_at timestamp without time zone,
    organization_id uuid NOT NULL,
    CONSTRAINT member_order_constraint CHECK ((member1_id < member2_id))
);


--
-- Name: dm_thread_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.dm_thread_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: dm_thread_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.dm_thread_id_seq OWNED BY public.dm_thread.id;


--
-- Name: document; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.document (
    id integer NOT NULL,
    uuid character varying(36) NOT NULL,
    filename character varying(255) NOT NULL,
    folder_id integer,
    mime_type character varying(100),
    size_bytes integer,
    created_at timestamp without time zone,
    updated_at timestamp without time zone,
    teamspace_id uuid,
    created_by_id integer,
    updated_by_id integer,
    organization_id uuid NOT NULL
);


--
-- Name: document_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.document_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: document_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.document_id_seq OWNED BY public.document.id;


--
-- Name: drive_connection; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.drive_connection (
    id integer NOT NULL,
    provider character varying(20) NOT NULL,
    connected_by_id integer NOT NULL,
    access_token text,
    refresh_token text,
    token_expires_at timestamp without time zone,
    connected_email character varying(255),
    selected_folders text,
    created_at timestamp without time zone,
    updated_at timestamp without time zone,
    teamspace_id uuid,
    organization_id uuid NOT NULL
);


--
-- Name: drive_connection_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.drive_connection_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: drive_connection_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.drive_connection_id_seq OWNED BY public.drive_connection.id;


--
-- Name: expense; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.expense (
    id integer NOT NULL,
    submitted_by_id integer NOT NULL,
    description character varying(255) NOT NULL,
    category public.expensecategory NOT NULL,
    amount numeric(10,2) NOT NULL,
    expense_date date NOT NULL,
    receipt_path character varying(500),
    notes text,
    job_id integer,
    billable_to_client boolean,
    paid_by public.paidby,
    status public.expensestatus,
    reviewed_by_id integer,
    reviewed_at timestamp without time zone,
    rejection_reason text,
    reimbursement_status public.reimbursementstatus,
    reimbursed_at timestamp without time zone,
    reimbursement_method character varying(50),
    reimbursement_reference character varying(100),
    reimbursed_by_id integer,
    invoiced boolean,
    invoice_line_item_id integer,
    synced_to_accounting boolean,
    created_at timestamp without time zone,
    updated_at timestamp without time zone,
    teamspace_id uuid,
    organization_id uuid NOT NULL
);


--
-- Name: expense_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.expense_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: expense_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.expense_id_seq OWNED BY public.expense.id;


--
-- Name: folder; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.folder (
    id integer NOT NULL,
    name character varying(255) NOT NULL,
    parent_id integer,
    created_at timestamp without time zone,
    updated_at timestamp without time zone,
    teamspace_id uuid,
    created_by_id integer,
    updated_by_id integer,
    organization_id uuid NOT NULL
);


--
-- Name: folder_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.folder_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: folder_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.folder_id_seq OWNED BY public.folder.id;


--
-- Name: interview; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.interview (
    id integer NOT NULL,
    created_at timestamp without time zone,
    updated_at timestamp without time zone,
    application_id integer NOT NULL,
    interview_type public.interviewtype,
    status public.interviewstatus,
    scheduled_at timestamp without time zone NOT NULL,
    duration_minutes integer,
    location character varying(500),
    interviewer_id integer,
    feedback text,
    recommendation public.interviewrecommendation,
    completed_at timestamp without time zone,
    teamspace_id uuid,
    created_by_id integer,
    updated_by_id integer,
    organization_id uuid NOT NULL
);


--
-- Name: interview_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.interview_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: interview_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.interview_id_seq OWNED BY public.interview.id;


--
-- Name: job_posting; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.job_posting (
    id integer NOT NULL,
    created_at timestamp without time zone,
    updated_at timestamp without time zone,
    title character varying(200) NOT NULL,
    department character varying(100),
    location character varying(200),
    job_type public.jobtype,
    salary_min numeric(10,2),
    salary_max numeric(10,2),
    description text,
    requirements text,
    status public.jobstatus,
    published_at timestamp without time zone,
    closed_at timestamp without time zone,
    hiring_manager_id integer,
    teamspace_id uuid,
    created_by_id integer,
    updated_by_id integer,
    organization_id uuid NOT NULL
);


--
-- Name: job_posting_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.job_posting_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: job_posting_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.job_posting_id_seq OWNED BY public.job_posting.id;


--
-- Name: kb_article; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.kb_article (
    id integer NOT NULL,
    category_id integer NOT NULL,
    subcategory_id integer,
    title character varying(500) NOT NULL,
    slug character varying(500) NOT NULL,
    content text NOT NULL,
    excerpt character varying(500),
    is_public boolean,
    is_active boolean,
    sort_order integer,
    view_count integer,
    created_at timestamp without time zone,
    updated_at timestamp without time zone,
    teamspace_id uuid,
    created_by_id integer,
    updated_by_id integer,
    organization_id uuid NOT NULL
);


--
-- Name: kb_article_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.kb_article_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: kb_article_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.kb_article_id_seq OWNED BY public.kb_article.id;


--
-- Name: kb_category; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.kb_category (
    id integer NOT NULL,
    name character varying(255) NOT NULL,
    slug character varying(255) NOT NULL,
    description text,
    icon_class character varying(100),
    sort_order integer,
    is_active boolean,
    created_at timestamp without time zone,
    updated_at timestamp without time zone,
    teamspace_id uuid,
    created_by_id integer,
    updated_by_id integer,
    organization_id uuid NOT NULL
);


--
-- Name: kb_category_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.kb_category_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: kb_category_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.kb_category_id_seq OWNED BY public.kb_category.id;


--
-- Name: kb_feedback; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.kb_feedback (
    id integer NOT NULL,
    article_id integer NOT NULL,
    is_helpful boolean NOT NULL,
    comment text,
    user_id integer,
    session_id character varying(100),
    created_at timestamp without time zone,
    teamspace_id uuid,
    organization_id uuid NOT NULL
);


--
-- Name: kb_feedback_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.kb_feedback_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: kb_feedback_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.kb_feedback_id_seq OWNED BY public.kb_feedback.id;


--
-- Name: kb_subcategory; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.kb_subcategory (
    id integer NOT NULL,
    category_id integer NOT NULL,
    name character varying(255) NOT NULL,
    slug character varying(255) NOT NULL,
    description text,
    sort_order integer,
    is_active boolean,
    created_at timestamp without time zone,
    updated_at timestamp without time zone,
    teamspace_id uuid,
    created_by_id integer,
    updated_by_id integer,
    organization_id uuid NOT NULL
);


--
-- Name: kb_subcategory_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.kb_subcategory_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: kb_subcategory_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.kb_subcategory_id_seq OWNED BY public.kb_subcategory.id;


--
-- Name: leave_request; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.leave_request (
    id integer NOT NULL,
    member_id integer NOT NULL,
    leave_type public.leavetype NOT NULL,
    start_date date NOT NULL,
    end_date date NOT NULL,
    employee_notes text,
    status public.leaverequeststatus NOT NULL,
    submitted_at timestamp without time zone,
    admin_notes text,
    reviewed_by_id integer,
    reviewed_at timestamp without time zone,
    created_at timestamp without time zone NOT NULL,
    updated_at timestamp without time zone NOT NULL,
    teamspace_id uuid,
    created_by_id integer,
    updated_by_id integer,
    organization_id uuid NOT NULL
);


--
-- Name: leave_request_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.leave_request_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: leave_request_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.leave_request_id_seq OWNED BY public.leave_request.id;


--
-- Name: log_entry; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.log_entry (
    id integer NOT NULL,
    "timestamp" timestamp without time zone NOT NULL,
    level character varying(10) NOT NULL,
    message text NOT NULL,
    module character varying(100),
    request_id character varying(50)
);


--
-- Name: log_entry_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.log_entry_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: log_entry_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.log_entry_id_seq OWNED BY public.log_entry.id;


--
-- Name: note; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.note (
    id integer NOT NULL,
    member_id integer NOT NULL,
    title character varying(255),
    content text,
    visibility character varying(20) NOT NULL,
    is_pinned boolean,
    created_at timestamp without time zone,
    updated_at timestamp without time zone,
    teamspace_id uuid,
    organization_id uuid NOT NULL
);


--
-- Name: note_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.note_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: note_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.note_id_seq OWNED BY public.note.id;


--
-- Name: oauth_connection; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.oauth_connection (
    id integer NOT NULL,
    user_id integer NOT NULL,
    provider character varying(50) NOT NULL,
    provider_user_id character varying(255) NOT NULL,
    email character varying(255),
    access_token text,
    refresh_token text,
    token_type character varying(50),
    token_expires_at timestamp without time zone,
    scopes character varying(500),
    created_at timestamp without time zone,
    updated_at timestamp without time zone,
    teamspace_id uuid,
    organization_id uuid NOT NULL
);


--
-- Name: oauth_connection_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.oauth_connection_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: oauth_connection_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.oauth_connection_id_seq OWNED BY public.oauth_connection.id;


--
-- Name: offboarding_assignment; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.offboarding_assignment (
    id integer NOT NULL,
    member_id integer NOT NULL,
    task_id integer NOT NULL,
    completed boolean,
    completed_at timestamp without time zone,
    completed_by_id integer,
    created_at timestamp without time zone,
    teamspace_id uuid,
    organization_id uuid NOT NULL
);


--
-- Name: offboarding_assignment_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.offboarding_assignment_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: offboarding_assignment_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.offboarding_assignment_id_seq OWNED BY public.offboarding_assignment.id;


--
-- Name: offboarding_task; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.offboarding_task (
    id integer NOT NULL,
    name character varying(100) NOT NULL,
    description text,
    "order" integer,
    is_active boolean,
    created_at timestamp without time zone,
    updated_at timestamp without time zone,
    teamspace_id uuid,
    organization_id uuid NOT NULL
);


--
-- Name: offboarding_task_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.offboarding_task_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: offboarding_task_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.offboarding_task_id_seq OWNED BY public.offboarding_task.id;


--
-- Name: onboarding_record; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.onboarding_record (
    id integer NOT NULL,
    member_id integer,
    first_name character varying(100) NOT NULL,
    last_name character varying(100) NOT NULL,
    personal_email character varying(255) NOT NULL,
    work_email character varying(255),
    onboarding_type public.onboardingtype NOT NULL,
    "position" character varying(100),
    department character varying(100),
    start_date date,
    salary numeric(10,2),
    salary_type public.salarytype,
    manager_id integer,
    status public.onboardingstatus,
    token character varying(64),
    sent_at timestamp without time zone,
    started_at timestamp without time zone,
    submitted_at timestamp without time zone,
    completed_at timestamp without time zone,
    offer_letter_request_id integer,
    contract_request_id integer,
    tax_form_attachment_id integer,
    admin_notes text,
    created_at timestamp without time zone,
    updated_at timestamp without time zone,
    teamspace_id uuid,
    created_by_id integer,
    updated_by_id integer,
    organization_id uuid NOT NULL
);


--
-- Name: onboarding_record_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.onboarding_record_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: onboarding_record_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.onboarding_record_id_seq OWNED BY public.onboarding_record.id;


--
-- Name: onboarding_task; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.onboarding_task (
    id integer NOT NULL,
    onboarding_id integer NOT NULL,
    task_key character varying(50) NOT NULL,
    label character varying(100) NOT NULL,
    description text,
    assignee public.taskassignee NOT NULL,
    required boolean,
    "order" integer,
    status public.taskstatus,
    completed_at timestamp without time zone,
    data text,
    teamspace_id uuid,
    organization_id uuid NOT NULL
);


--
-- Name: onboarding_task_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.onboarding_task_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: onboarding_task_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.onboarding_task_id_seq OWNED BY public.onboarding_task.id;


--
-- Name: onboarding_task_template; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.onboarding_task_template (
    id integer NOT NULL,
    onboarding_type public.onboardingtype NOT NULL,
    task_key character varying(50) NOT NULL,
    label character varying(100) NOT NULL,
    description text,
    assignee public.taskassignee NOT NULL,
    required boolean,
    "order" integer,
    active boolean,
    created_at timestamp without time zone,
    updated_at timestamp without time zone,
    teamspace_id uuid,
    organization_id uuid NOT NULL
);


--
-- Name: onboarding_task_template_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.onboarding_task_template_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: onboarding_task_template_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.onboarding_task_template_id_seq OWNED BY public.onboarding_task_template.id;


--
-- Name: one_on_one_agenda_item; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.one_on_one_agenda_item (
    id integer NOT NULL,
    pair_id integer NOT NULL,
    session_id integer,
    added_by_id integer NOT NULL,
    content text NOT NULL,
    is_action_item boolean DEFAULT false NOT NULL,
    owner_id integer,
    completed boolean DEFAULT false NOT NULL,
    created_at timestamp without time zone DEFAULT now() NOT NULL,
    teamspace_id uuid,
    organization_id uuid NOT NULL
);


--
-- Name: one_on_one_agenda_item_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.one_on_one_agenda_item_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: one_on_one_agenda_item_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.one_on_one_agenda_item_id_seq OWNED BY public.one_on_one_agenda_item.id;


--
-- Name: one_on_one_pair; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.one_on_one_pair (
    id integer NOT NULL,
    lead_id integer NOT NULL,
    report_id integer NOT NULL,
    cadence character varying(20) DEFAULT 'biweekly'::character varying NOT NULL,
    next_meeting_date date,
    active boolean DEFAULT true NOT NULL,
    created_at timestamp without time zone DEFAULT now() NOT NULL,
    teamspace_id uuid,
    organization_id uuid NOT NULL
);


--
-- Name: one_on_one_pair_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.one_on_one_pair_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: one_on_one_pair_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.one_on_one_pair_id_seq OWNED BY public.one_on_one_pair.id;


--
-- Name: one_on_one_session; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.one_on_one_session (
    id integer NOT NULL,
    pair_id integer NOT NULL,
    meeting_date date NOT NULL,
    notes text,
    created_at timestamp without time zone DEFAULT now() NOT NULL,
    teamspace_id uuid,
    organization_id uuid NOT NULL
);


--
-- Name: one_on_one_session_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.one_on_one_session_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: one_on_one_session_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.one_on_one_session_id_seq OWNED BY public.one_on_one_session.id;


--
-- Name: organization; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.organization (
    id uuid NOT NULL,
    name character varying(255) NOT NULL,
    slug character varying(100) NOT NULL,
    owner_id integer,
    plan character varying(50),
    stripe_customer_id character varying(255),
    is_active boolean NOT NULL,
    phone character varying(50),
    email character varying(255),
    website character varying(255),
    address character varying(255),
    address_2 character varying(255),
    city character varying(100),
    state character varying(100),
    zip_code character varying(20),
    country character varying(100),
    tax_id character varying(100),
    created_at timestamp without time zone,
    updated_at timestamp without time zone,
    claimed_domain character varying(253)
);


--
-- Name: organization_invitation; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.organization_invitation (
    id integer NOT NULL,
    organization_id uuid NOT NULL,
    email character varying(255) NOT NULL,
    invited_by_id integer,
    role character varying(20) DEFAULT 'member'::character varying NOT NULL,
    token character varying(100) NOT NULL,
    expires_at timestamp without time zone NOT NULL,
    created_at timestamp without time zone DEFAULT now() NOT NULL,
    accepted_at timestamp without time zone
);


--
-- Name: organization_invitation_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.organization_invitation_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: organization_invitation_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.organization_invitation_id_seq OWNED BY public.organization_invitation.id;


--
-- Name: organization_user; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.organization_user (
    id integer NOT NULL,
    organization_id uuid NOT NULL,
    user_id integer NOT NULL,
    role character varying(20) DEFAULT 'member'::character varying NOT NULL,
    is_active boolean DEFAULT true NOT NULL,
    joined_at timestamp without time zone DEFAULT now() NOT NULL,
    invited_by_id integer,
    created_at timestamp without time zone DEFAULT now(),
    updated_at timestamp without time zone DEFAULT now(),
    auto_join_banner_dismissed boolean DEFAULT false NOT NULL
);


--
-- Name: organization_user_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.organization_user_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: organization_user_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.organization_user_id_seq OWNED BY public.organization_user.id;


--
-- Name: pending_signup; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.pending_signup (
    id integer NOT NULL,
    email character varying(120) NOT NULL,
    password_hash character varying(200),
    first_name character varying(50),
    last_name character varying(50),
    token character varying(100) NOT NULL,
    expires_at timestamp without time zone NOT NULL,
    created_at timestamp without time zone,
    organization_name character varying(255)
);


--
-- Name: pending_signup_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.pending_signup_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: pending_signup_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.pending_signup_id_seq OWNED BY public.pending_signup.id;


--
-- Name: person_note; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.person_note (
    id integer NOT NULL,
    member_id integer NOT NULL,
    content text NOT NULL,
    created_at timestamp without time zone,
    updated_at timestamp without time zone,
    teamspace_id uuid,
    created_by_id integer,
    updated_by_id integer,
    deleted_at timestamp without time zone,
    deleted_by_id integer,
    organization_id uuid NOT NULL
);


--
-- Name: person_note_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.person_note_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: person_note_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.person_note_id_seq OWNED BY public.person_note.id;


--
-- Name: presence_settings; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.presence_settings (
    id integer NOT NULL,
    time_clock_enabled boolean,
    rounding_enabled boolean,
    rounding_minutes integer,
    rounding_type character varying(20),
    board_enabled boolean,
    board_visible_to_all boolean,
    public_board_token character varying(64),
    auto_close_enabled boolean,
    auto_close_after_hours integer,
    geofence_enabled boolean,
    geofence_enforcement character varying(10),
    geofence_use_company_address boolean,
    geofence_latitude double precision,
    geofence_longitude double precision,
    geofence_radius_meters integer,
    geofence_address character varying(255),
    geofence_city character varying(100),
    geofence_state character varying(100),
    geofence_zip character varying(20),
    flow_reset_time character varying(5),
    pulse_nudge_enabled boolean,
    pulse_nudge_time character varying(5),
    eod_nudge_enabled boolean,
    eod_nudge_time character varying(5),
    updated_at timestamp without time zone,
    notify_on_submission boolean,
    teamspace_id uuid,
    organization_id uuid NOT NULL
);


--
-- Name: presence_settings_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.presence_settings_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: presence_settings_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.presence_settings_id_seq OWNED BY public.presence_settings.id;


--
-- Name: presence_signal; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.presence_signal (
    id integer NOT NULL,
    teamspace_id uuid NOT NULL,
    member_id integer NOT NULL,
    template_id integer NOT NULL,
    value character varying(50) NOT NULL,
    created_at timestamp without time zone DEFAULT now() NOT NULL,
    ended_at timestamp without time zone,
    source_post_id integer
);


--
-- Name: presence_signal_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.presence_signal_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: presence_signal_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.presence_signal_id_seq OWNED BY public.presence_signal.id;


--
-- Name: project; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.project (
    id integer NOT NULL,
    teamspace_id uuid,
    name character varying(200) NOT NULL,
    description character varying(500),
    status character varying(20) DEFAULT 'active'::character varying NOT NULL,
    color character varying(10),
    emoji character varying(10),
    owner_id integer,
    channel_id integer,
    archived_at timestamp without time zone,
    created_by_id integer,
    created_at timestamp without time zone DEFAULT now() NOT NULL,
    updated_at timestamp without time zone DEFAULT now() NOT NULL,
    is_private boolean DEFAULT false NOT NULL,
    organization_id uuid NOT NULL
);


--
-- Name: project_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.project_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: project_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.project_id_seq OWNED BY public.project.id;


--
-- Name: punch_change_request; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.punch_change_request (
    id integer NOT NULL,
    clock_punch_id integer NOT NULL,
    member_id integer NOT NULL,
    original_time timestamp without time zone NOT NULL,
    requested_time timestamp without time zone NOT NULL,
    reason text,
    status public.punchcorrectionrequeststatus NOT NULL,
    admin_notes text,
    reviewed_by_id integer,
    reviewed_at timestamp without time zone,
    created_at timestamp without time zone NOT NULL,
    teamspace_id uuid,
    created_by_id integer,
    updated_by_id integer,
    organization_id uuid NOT NULL
);


--
-- Name: punch_change_request_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.punch_change_request_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: punch_change_request_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.punch_change_request_id_seq OWNED BY public.punch_change_request.id;


--
-- Name: push_subscription; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.push_subscription (
    id integer NOT NULL,
    user_id integer NOT NULL,
    endpoint character varying(500) NOT NULL,
    auth_key character varying(100) NOT NULL,
    p256dh_key character varying(100) NOT NULL,
    is_active boolean,
    created_at timestamp without time zone,
    updated_at timestamp without time zone,
    teamspace_id uuid,
    organization_id uuid NOT NULL
);


--
-- Name: push_subscription_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.push_subscription_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: push_subscription_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.push_subscription_id_seq OWNED BY public.push_subscription.id;


--
-- Name: refresh_token; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.refresh_token (
    id integer NOT NULL,
    user_id integer NOT NULL,
    token_hash character varying(64) NOT NULL,
    expires_at timestamp without time zone NOT NULL,
    revoked_at timestamp without time zone,
    created_at timestamp without time zone,
    device_info character varying(255)
);


--
-- Name: refresh_token_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.refresh_token_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: refresh_token_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.refresh_token_id_seq OWNED BY public.refresh_token.id;


--
-- Name: resources_settings; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.resources_settings (
    id integer NOT NULL,
    esign_enabled boolean,
    esign_default_expiry_days integer,
    esign_reminder_days integer,
    esign_company_name character varying(255),
    updated_at timestamp without time zone,
    teamspace_id uuid,
    organization_id uuid NOT NULL
);


--
-- Name: resources_settings_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.resources_settings_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: resources_settings_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.resources_settings_id_seq OWNED BY public.resources_settings.id;


--
-- Name: service_location; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.service_location (
    id integer NOT NULL,
    contact_id integer NOT NULL,
    name character varying(100) NOT NULL,
    address character varying(255),
    address_2 character varying(255),
    city character varying(100),
    state character varying(100),
    zip_code character varying(20),
    country character varying(100),
    access_notes text,
    gate_code character varying(50),
    is_default boolean,
    lat double precision,
    lng double precision,
    created_at timestamp without time zone,
    updated_at timestamp without time zone,
    teamspace_id uuid,
    organization_id uuid NOT NULL
);


--
-- Name: service_location_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.service_location_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: service_location_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.service_location_id_seq OWNED BY public.service_location.id;


--
-- Name: signature_audit_log; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.signature_audit_log (
    id integer NOT NULL,
    request_id integer NOT NULL,
    event_type character varying(30) NOT NULL,
    actor_email character varying(255),
    actor_user_id integer,
    recipient_id integer,
    "timestamp" timestamp without time zone,
    ip_address character varying(45),
    user_agent character varying(500),
    details text,
    teamspace_id uuid,
    organization_id uuid NOT NULL
);


--
-- Name: signature_audit_log_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.signature_audit_log_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: signature_audit_log_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.signature_audit_log_id_seq OWNED BY public.signature_audit_log.id;


--
-- Name: signature_recipient; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.signature_recipient (
    id integer NOT NULL,
    request_id integer NOT NULL,
    email character varying(255) NOT NULL,
    name character varying(255) NOT NULL,
    role character varying(20),
    "order" integer,
    token character varying(64) NOT NULL,
    status character varying(20),
    signed_name character varying(255),
    signed_at timestamp without time zone,
    ip_address character varying(45),
    user_agent character varying(500),
    device_info text,
    geo_latitude double precision,
    geo_longitude double precision,
    geo_accuracy double precision,
    geo_location_name character varying(255),
    user_id integer,
    last_notified_at timestamp without time zone,
    notification_count integer,
    teamspace_id uuid,
    organization_id uuid NOT NULL
);


--
-- Name: signature_recipient_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.signature_recipient_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: signature_recipient_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.signature_recipient_id_seq OWNED BY public.signature_recipient.id;


--
-- Name: signature_request; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.signature_request (
    id integer NOT NULL,
    uuid character varying(36) NOT NULL,
    title character varying(255) NOT NULL,
    message text,
    original_attachment_id integer,
    original_document_hash character varying(64) NOT NULL,
    signed_attachment_id integer,
    status character varying(20),
    created_by_id integer,
    created_at timestamp without time zone,
    completed_at timestamp without time zone,
    expires_at timestamp without time zone,
    context text,
    callback_url character varying(255),
    teamspace_id uuid,
    organization_id uuid NOT NULL
);


--
-- Name: signature_request_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.signature_request_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: signature_request_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.signature_request_id_seq OWNED BY public.signature_request.id;


--
-- Name: update_area; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.update_area (
    id integer NOT NULL,
    teamspace_id uuid,
    name character varying(100) NOT NULL,
    color character varying(7) DEFAULT '#6b7280'::character varying NOT NULL,
    emoji character varying(10),
    sort_order integer DEFAULT 0 NOT NULL,
    is_active boolean DEFAULT true NOT NULL,
    created_at timestamp without time zone DEFAULT now() NOT NULL,
    organization_id uuid NOT NULL
);


--
-- Name: sync_area_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.sync_area_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: sync_area_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.sync_area_id_seq OWNED BY public.update_area.id;


--
-- Name: update_post_ack; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.update_post_ack (
    id integer NOT NULL,
    teamspace_id uuid,
    post_id integer NOT NULL,
    member_id integer NOT NULL,
    created_at timestamp without time zone,
    organization_id uuid NOT NULL
);


--
-- Name: sync_post_ack_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.sync_post_ack_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: sync_post_ack_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.sync_post_ack_id_seq OWNED BY public.update_post_ack.id;


--
-- Name: update_week_review; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.update_week_review (
    id integer NOT NULL,
    week_start date NOT NULL,
    week_end date NOT NULL,
    content text,
    status character varying(20) DEFAULT 'draft'::character varying NOT NULL,
    sent_at timestamp without time zone,
    sent_by_id integer,
    post_id integer,
    created_at timestamp without time zone DEFAULT now() NOT NULL,
    teamspace_id uuid,
    organization_id uuid NOT NULL
);


--
-- Name: sync_week_review_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.sync_week_review_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: sync_week_review_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.sync_week_review_id_seq OWNED BY public.update_week_review.id;


--
-- Name: system_notification; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.system_notification (
    id integer NOT NULL,
    created_at timestamp without time zone,
    target_role character varying(50),
    user_id integer,
    type character varying(50),
    title character varying(200) NOT NULL,
    message text,
    icon character varying(50),
    color character varying(20),
    action_url character varying(500),
    is_read boolean,
    is_dismissed boolean,
    teamspace_id uuid,
    organization_id uuid NOT NULL
);


--
-- Name: system_notification_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.system_notification_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: system_notification_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.system_notification_id_seq OWNED BY public.system_notification.id;


--
-- Name: tax_form_record; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.tax_form_record (
    id integer NOT NULL,
    member_id integer NOT NULL,
    form_type character varying(20) NOT NULL,
    tax_year integer NOT NULL,
    nonemployee_compensation numeric(10,2) NOT NULL,
    federal_tax_withheld numeric(10,2),
    created_at timestamp without time zone,
    created_by_id integer NOT NULL,
    attachment_id integer,
    teamspace_id uuid,
    organization_id uuid NOT NULL
);


--
-- Name: tax_form_record_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.tax_form_record_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: tax_form_record_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.tax_form_record_id_seq OWNED BY public.tax_form_record.id;


--
-- Name: teamspace; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.teamspace (
    id uuid NOT NULL,
    slug character varying(100) NOT NULL,
    name character varying(255) NOT NULL,
    plan character varying(50),
    organization_id uuid,
    is_active boolean NOT NULL,
    created_at timestamp without time zone,
    updated_at timestamp without time zone,
    color character varying(10) NOT NULL,
    deleted_at timestamp without time zone,
    deleted_by_id integer
);


--
-- Name: teamspace_invite; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.teamspace_invite (
    id integer NOT NULL,
    teamspace_id uuid,
    email character varying(255) NOT NULL,
    invited_by_id integer,
    token character varying(64) NOT NULL,
    token_expires timestamp without time zone NOT NULL,
    status public.invitestatus DEFAULT 'PENDING'::public.invitestatus NOT NULL,
    accepted_at timestamp without time zone,
    created_at timestamp without time zone DEFAULT now(),
    created_by_id integer,
    updated_by_id integer,
    updated_at timestamp without time zone,
    scoped_teamspace_ids uuid[],
    invite_all_teamspaces boolean DEFAULT false NOT NULL,
    organization_id uuid NOT NULL
);


--
-- Name: teamspace_invite_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.teamspace_invite_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: teamspace_invite_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.teamspace_invite_id_seq OWNED BY public.teamspace_invite.id;


--
-- Name: teamspace_settings; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.teamspace_settings (
    id integer NOT NULL,
    company_name character varying(255),
    default_language character varying(5),
    timezone character varying(50),
    date_format character varying(20),
    time_format character varying(20),
    currency character varying(10),
    first_day_of_week integer,
    industry public.industry,
    email_provider character varying(50),
    email_host character varying(255),
    email_port integer,
    email_username character varying(255),
    email_password character varying(255),
    email_from character varying(255),
    site_id character varying(64),
    sparqmail_api_key character varying(255),
    sms_provider character varying(50),
    pending_service character varying(20),
    onboarding_completed boolean,
    is_demo boolean,
    email_verified boolean,
    setup_completed boolean,
    sidebar_config text,
    updated_at timestamp without time zone,
    teamspace_id uuid,
    action_items_tier_labels json,
    sync_label_config json,
    organization_id uuid NOT NULL
);


--
-- Name: teamspace_settings_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.teamspace_settings_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: teamspace_settings_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.teamspace_settings_id_seq OWNED BY public.teamspace_settings.id;


--
-- Name: teamspace_user; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.teamspace_user (
    id integer NOT NULL,
    user_id integer NOT NULL,
    role character varying(20) NOT NULL,
    permissions text NOT NULL,
    employee_id character varying(20),
    department character varying(100),
    "position" character varying(100),
    status public.employeestatus,
    type public.employeetype,
    start_date date,
    salary numeric(10,2),
    salary_type public.salarytype,
    labor_cost_rate numeric(10,2),
    bill_rate numeric(10,2),
    phone character varying(20),
    clock_pin character varying(4),
    termination_date date,
    termination_reason public.terminationreason,
    bio text,
    working_style text,
    intro_posted boolean,
    manager_id integer,
    teamspace_id uuid,
    open_door_until timestamp without time zone,
    deleted_at timestamp without time zone,
    deleted_by_id integer,
    organization_user_id integer,
    member_type character varying(20) DEFAULT 'full'::character varying NOT NULL,
    organization_id uuid NOT NULL
);


--
-- Name: teamspace_user_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.teamspace_user_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: teamspace_user_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.teamspace_user_id_seq OWNED BY public.teamspace_user.id;


--
-- Name: time_entry; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.time_entry (
    id integer NOT NULL,
    member_id integer NOT NULL,
    date date NOT NULL,
    hours numeric(5,2) NOT NULL,
    description text,
    is_billable boolean NOT NULL,
    job_id integer,
    visit_id integer,
    task_id integer,
    category character varying(100),
    labor_cost_rate numeric(10,2),
    bill_rate numeric(10,2),
    labor_cost numeric(10,2),
    billing_amount numeric(10,2),
    status public.timeentrystatus NOT NULL,
    submitted_at timestamp without time zone,
    approved_by_id integer,
    approved_at timestamp without time zone,
    rejected_reason text,
    invoice_id integer,
    timer_start timestamp without time zone,
    timer_end timestamp without time zone,
    created_at timestamp without time zone NOT NULL,
    updated_at timestamp without time zone NOT NULL,
    teamspace_id uuid,
    created_by_id integer,
    updated_by_id integer,
    organization_id uuid NOT NULL
);


--
-- Name: time_entry_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.time_entry_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: time_entry_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.time_entry_id_seq OWNED BY public.time_entry.id;


--
-- Name: timesheet_notification_recipients; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.timesheet_notification_recipients (
    settings_id integer NOT NULL,
    user_id integer NOT NULL
);


--
-- Name: update_channel_read_state; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.update_channel_read_state (
    id integer NOT NULL,
    member_id integer NOT NULL,
    channel_id integer NOT NULL,
    last_read_post_id integer,
    updated_at timestamp without time zone DEFAULT now(),
    teamspace_id uuid,
    organization_id uuid NOT NULL
);


--
-- Name: update_channel_read_state_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.update_channel_read_state_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: update_channel_read_state_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.update_channel_read_state_id_seq OWNED BY public.update_channel_read_state.id;


--
-- Name: update_webhook; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.update_webhook (
    id integer NOT NULL,
    token character varying(64) NOT NULL,
    channel_id integer,
    dm_thread_id integer,
    webhook_type character varying(20) NOT NULL,
    github_secret character varying(100),
    is_active boolean NOT NULL,
    created_by_id integer NOT NULL,
    created_at timestamp without time zone,
    teamspace_id uuid,
    enable_ten_four boolean DEFAULT false,
    organization_id uuid NOT NULL,
    CONSTRAINT webhook_target_check CHECK ((((channel_id IS NOT NULL) AND (dm_thread_id IS NULL)) OR ((channel_id IS NULL) AND (dm_thread_id IS NOT NULL))))
);


--
-- Name: user; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public."user" (
    id integer NOT NULL,
    email character varying(120) NOT NULL,
    password_hash character varying(200),
    first_name character varying(50),
    last_name character varying(50),
    avatar_color character varying(7),
    created_at timestamp without time zone,
    is_active boolean,
    is_sample boolean,
    needs_password_setup boolean,
    password_reset_token character varying(100),
    password_reset_expires timestamp without time zone,
    magic_link_token character varying(100),
    magic_link_expires timestamp without time zone,
    phone_number character varying(20),
    phone_verified boolean,
    sms_otp character varying(6),
    sms_otp_expires timestamp without time zone,
    last_seen timestamp without time zone,
    birthday date,
    gender character varying(30),
    personal_phone character varying(20),
    address character varying(100),
    address_2 character varying(100),
    city character varying(50),
    state character varying(50),
    zip_code character varying(20),
    country character varying(50),
    emergency_contact_name character varying(100),
    emergency_contact_phone character varying(20),
    emergency_contact_relationship character varying(50),
    social_media character varying(100),
    failed_login_attempts integer NOT NULL,
    locked_until timestamp without time zone,
    last_failed_login timestamp without time zone,
    is_staff boolean DEFAULT false NOT NULL
);


--
-- Name: user_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.user_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: user_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.user_id_seq OWNED BY public."user".id;


--
-- Name: user_setting; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.user_setting (
    id integer NOT NULL,
    user_id integer NOT NULL,
    key character varying(255) NOT NULL,
    value text,
    created_at timestamp without time zone,
    updated_at timestamp without time zone,
    teamspace_id uuid,
    organization_id uuid NOT NULL
);


--
-- Name: user_setting_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.user_setting_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: user_setting_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.user_setting_id_seq OWNED BY public.user_setting.id;


--
-- Name: webhook_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.webhook_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: webhook_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.webhook_id_seq OWNED BY public.update_webhook.id;


--
-- Name: weekly_plan; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.weekly_plan (
    id integer NOT NULL,
    teamspace_id uuid,
    week_number integer NOT NULL,
    year integer NOT NULL,
    start_date date NOT NULL,
    end_date date NOT NULL,
    title character varying(200),
    description character varying(500),
    created_by_id integer,
    created_at timestamp without time zone DEFAULT now() NOT NULL,
    updated_at timestamp without time zone DEFAULT now() NOT NULL,
    organization_id uuid NOT NULL
);


--
-- Name: weekly_plan_goal; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.weekly_plan_goal (
    id integer NOT NULL,
    plan_id integer NOT NULL,
    text character varying(500) NOT NULL,
    sort_order integer DEFAULT 0 NOT NULL,
    is_complete boolean DEFAULT false NOT NULL,
    created_at timestamp without time zone DEFAULT now() NOT NULL
);


--
-- Name: weekly_plan_goal_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.weekly_plan_goal_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: weekly_plan_goal_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.weekly_plan_goal_id_seq OWNED BY public.weekly_plan_goal.id;


--
-- Name: weekly_plan_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.weekly_plan_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: weekly_plan_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.weekly_plan_id_seq OWNED BY public.weekly_plan.id;


--
-- Name: working_agreement; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.working_agreement (
    id integer NOT NULL,
    content text NOT NULL,
    version integer DEFAULT 1 NOT NULL,
    updated_by_id integer,
    created_at timestamp without time zone DEFAULT now() NOT NULL,
    updated_at timestamp without time zone DEFAULT now() NOT NULL,
    teamspace_id uuid,
    organization_id uuid NOT NULL
);


--
-- Name: working_agreement_ack; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.working_agreement_ack (
    id integer NOT NULL,
    agreement_id integer NOT NULL,
    member_id integer NOT NULL,
    version integer NOT NULL,
    acknowledged_at timestamp without time zone DEFAULT now() NOT NULL,
    teamspace_id uuid,
    organization_id uuid NOT NULL
);


--
-- Name: working_agreement_ack_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.working_agreement_ack_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: working_agreement_ack_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.working_agreement_ack_id_seq OWNED BY public.working_agreement_ack.id;


--
-- Name: working_agreement_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.working_agreement_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: working_agreement_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.working_agreement_id_seq OWNED BY public.working_agreement.id;


--
-- Name: accounting_account id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.accounting_account ALTER COLUMN id SET DEFAULT nextval('public.accounting_account_id_seq'::regclass);


--
-- Name: accounting_ledger id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.accounting_ledger ALTER COLUMN id SET DEFAULT nextval('public.accounting_ledger_id_seq'::regclass);


--
-- Name: action_item id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.action_item ALTER COLUMN id SET DEFAULT nextval('public.action_item_id_seq'::regclass);


--
-- Name: action_item_log id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.action_item_log ALTER COLUMN id SET DEFAULT nextval('public.action_item_log_id_seq'::regclass);


--
-- Name: activity_log id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.activity_log ALTER COLUMN id SET DEFAULT nextval('public.activity_log_id_seq'::regclass);


--
-- Name: ai_pending_action id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.ai_pending_action ALTER COLUMN id SET DEFAULT nextval('public.ai_pending_action_id_seq'::regclass);


--
-- Name: application id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.application ALTER COLUMN id SET DEFAULT nextval('public.application_id_seq'::regclass);


--
-- Name: application_activity id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.application_activity ALTER COLUMN id SET DEFAULT nextval('public.application_activity_id_seq'::regclass);


--
-- Name: attachment id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.attachment ALTER COLUMN id SET DEFAULT nextval('public.attachment_id_seq'::regclass);


--
-- Name: attachment_link id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.attachment_link ALTER COLUMN id SET DEFAULT nextval('public.attachment_link_id_seq'::regclass);


--
-- Name: audit_log id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.audit_log ALTER COLUMN id SET DEFAULT nextval('public.audit_log_id_seq'::regclass);


--
-- Name: auth_settings id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.auth_settings ALTER COLUMN id SET DEFAULT nextval('public.auth_settings_id_seq'::regclass);


--
-- Name: candidate id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.candidate ALTER COLUMN id SET DEFAULT nextval('public.candidate_id_seq'::regclass);


--
-- Name: canned_action id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.canned_action ALTER COLUMN id SET DEFAULT nextval('public.canned_action_id_seq'::regclass);


--
-- Name: clock_punch id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.clock_punch ALTER COLUMN id SET DEFAULT nextval('public.clock_punch_id_seq'::regclass);


--
-- Name: clock_punch_adjustment id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.clock_punch_adjustment ALTER COLUMN id SET DEFAULT nextval('public.clock_punch_adjustment_id_seq'::regclass);


--
-- Name: contact id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.contact ALTER COLUMN id SET DEFAULT nextval('public.contact_id_seq'::regclass);


--
-- Name: device_token id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.device_token ALTER COLUMN id SET DEFAULT nextval('public.device_token_id_seq'::regclass);


--
-- Name: dm id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.dm ALTER COLUMN id SET DEFAULT nextval('public.direct_message_id_seq'::regclass);


--
-- Name: dm_ack id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.dm_ack ALTER COLUMN id SET DEFAULT nextval('public.dm_acknowledgment_id_seq'::regclass);


--
-- Name: dm_reaction id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.dm_reaction ALTER COLUMN id SET DEFAULT nextval('public.dm_reaction_id_seq'::regclass);


--
-- Name: dm_thread id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.dm_thread ALTER COLUMN id SET DEFAULT nextval('public.dm_thread_id_seq'::regclass);


--
-- Name: document id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.document ALTER COLUMN id SET DEFAULT nextval('public.document_id_seq'::regclass);


--
-- Name: drive_connection id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.drive_connection ALTER COLUMN id SET DEFAULT nextval('public.drive_connection_id_seq'::regclass);


--
-- Name: event id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.event ALTER COLUMN id SET DEFAULT nextval('public.company_event_id_seq'::regclass);


--
-- Name: expense id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.expense ALTER COLUMN id SET DEFAULT nextval('public.expense_id_seq'::regclass);


--
-- Name: folder id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.folder ALTER COLUMN id SET DEFAULT nextval('public.folder_id_seq'::regclass);


--
-- Name: interview id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.interview ALTER COLUMN id SET DEFAULT nextval('public.interview_id_seq'::regclass);


--
-- Name: job_posting id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.job_posting ALTER COLUMN id SET DEFAULT nextval('public.job_posting_id_seq'::regclass);


--
-- Name: kb_article id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.kb_article ALTER COLUMN id SET DEFAULT nextval('public.kb_article_id_seq'::regclass);


--
-- Name: kb_category id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.kb_category ALTER COLUMN id SET DEFAULT nextval('public.kb_category_id_seq'::regclass);


--
-- Name: kb_feedback id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.kb_feedback ALTER COLUMN id SET DEFAULT nextval('public.kb_feedback_id_seq'::regclass);


--
-- Name: kb_subcategory id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.kb_subcategory ALTER COLUMN id SET DEFAULT nextval('public.kb_subcategory_id_seq'::regclass);


--
-- Name: leave_request id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.leave_request ALTER COLUMN id SET DEFAULT nextval('public.leave_request_id_seq'::regclass);


--
-- Name: log_entry id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.log_entry ALTER COLUMN id SET DEFAULT nextval('public.log_entry_id_seq'::regclass);


--
-- Name: note id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.note ALTER COLUMN id SET DEFAULT nextval('public.note_id_seq'::regclass);


--
-- Name: oauth_connection id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.oauth_connection ALTER COLUMN id SET DEFAULT nextval('public.oauth_connection_id_seq'::regclass);


--
-- Name: offboarding_assignment id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.offboarding_assignment ALTER COLUMN id SET DEFAULT nextval('public.offboarding_assignment_id_seq'::regclass);


--
-- Name: offboarding_task id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.offboarding_task ALTER COLUMN id SET DEFAULT nextval('public.offboarding_task_id_seq'::regclass);


--
-- Name: onboarding_record id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.onboarding_record ALTER COLUMN id SET DEFAULT nextval('public.onboarding_record_id_seq'::regclass);


--
-- Name: onboarding_task id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.onboarding_task ALTER COLUMN id SET DEFAULT nextval('public.onboarding_task_id_seq'::regclass);


--
-- Name: onboarding_task_template id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.onboarding_task_template ALTER COLUMN id SET DEFAULT nextval('public.onboarding_task_template_id_seq'::regclass);


--
-- Name: one_on_one_agenda_item id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.one_on_one_agenda_item ALTER COLUMN id SET DEFAULT nextval('public.one_on_one_agenda_item_id_seq'::regclass);


--
-- Name: one_on_one_pair id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.one_on_one_pair ALTER COLUMN id SET DEFAULT nextval('public.one_on_one_pair_id_seq'::regclass);


--
-- Name: one_on_one_session id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.one_on_one_session ALTER COLUMN id SET DEFAULT nextval('public.one_on_one_session_id_seq'::regclass);


--
-- Name: organization_invitation id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.organization_invitation ALTER COLUMN id SET DEFAULT nextval('public.organization_invitation_id_seq'::regclass);


--
-- Name: organization_user id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.organization_user ALTER COLUMN id SET DEFAULT nextval('public.organization_user_id_seq'::regclass);


--
-- Name: pending_signup id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.pending_signup ALTER COLUMN id SET DEFAULT nextval('public.pending_signup_id_seq'::regclass);


--
-- Name: person_note id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.person_note ALTER COLUMN id SET DEFAULT nextval('public.person_note_id_seq'::regclass);


--
-- Name: presence_settings id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.presence_settings ALTER COLUMN id SET DEFAULT nextval('public.presence_settings_id_seq'::regclass);


--
-- Name: presence_signal id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.presence_signal ALTER COLUMN id SET DEFAULT nextval('public.presence_signal_id_seq'::regclass);


--
-- Name: project id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.project ALTER COLUMN id SET DEFAULT nextval('public.project_id_seq'::regclass);


--
-- Name: punch_change_request id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.punch_change_request ALTER COLUMN id SET DEFAULT nextval('public.punch_change_request_id_seq'::regclass);


--
-- Name: push_subscription id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.push_subscription ALTER COLUMN id SET DEFAULT nextval('public.push_subscription_id_seq'::regclass);


--
-- Name: refresh_token id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.refresh_token ALTER COLUMN id SET DEFAULT nextval('public.refresh_token_id_seq'::regclass);


--
-- Name: resources_settings id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.resources_settings ALTER COLUMN id SET DEFAULT nextval('public.resources_settings_id_seq'::regclass);


--
-- Name: service_location id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.service_location ALTER COLUMN id SET DEFAULT nextval('public.service_location_id_seq'::regclass);


--
-- Name: signature_audit_log id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.signature_audit_log ALTER COLUMN id SET DEFAULT nextval('public.signature_audit_log_id_seq'::regclass);


--
-- Name: signature_recipient id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.signature_recipient ALTER COLUMN id SET DEFAULT nextval('public.signature_recipient_id_seq'::regclass);


--
-- Name: signature_request id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.signature_request ALTER COLUMN id SET DEFAULT nextval('public.signature_request_id_seq'::regclass);


--
-- Name: system_notification id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.system_notification ALTER COLUMN id SET DEFAULT nextval('public.system_notification_id_seq'::regclass);


--
-- Name: tax_form_record id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.tax_form_record ALTER COLUMN id SET DEFAULT nextval('public.tax_form_record_id_seq'::regclass);


--
-- Name: teamspace_invite id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.teamspace_invite ALTER COLUMN id SET DEFAULT nextval('public.teamspace_invite_id_seq'::regclass);


--
-- Name: teamspace_settings id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.teamspace_settings ALTER COLUMN id SET DEFAULT nextval('public.teamspace_settings_id_seq'::regclass);


--
-- Name: teamspace_user id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.teamspace_user ALTER COLUMN id SET DEFAULT nextval('public.teamspace_user_id_seq'::regclass);


--
-- Name: time_entry id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.time_entry ALTER COLUMN id SET DEFAULT nextval('public.time_entry_id_seq'::regclass);


--
-- Name: update_area id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.update_area ALTER COLUMN id SET DEFAULT nextval('public.sync_area_id_seq'::regclass);


--
-- Name: update_channel id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.update_channel ALTER COLUMN id SET DEFAULT nextval('public.channel_id_seq'::regclass);


--
-- Name: update_channel_read_state id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.update_channel_read_state ALTER COLUMN id SET DEFAULT nextval('public.update_channel_read_state_id_seq'::regclass);


--
-- Name: update_follow id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.update_follow ALTER COLUMN id SET DEFAULT nextval('public.content_follow_id_seq'::regclass);


--
-- Name: update_nudge_log id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.update_nudge_log ALTER COLUMN id SET DEFAULT nextval('public.connect_nudge_log_id_seq'::regclass);


--
-- Name: update_post id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.update_post ALTER COLUMN id SET DEFAULT nextval('public.connect_post_id_seq'::regclass);


--
-- Name: update_post_ack id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.update_post_ack ALTER COLUMN id SET DEFAULT nextval('public.sync_post_ack_id_seq'::regclass);


--
-- Name: update_post_reaction id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.update_post_reaction ALTER COLUMN id SET DEFAULT nextval('public.connect_post_reaction_id_seq'::regclass);


--
-- Name: update_template id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.update_template ALTER COLUMN id SET DEFAULT nextval('public.connect_template_id_seq'::regclass);


--
-- Name: update_webhook id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.update_webhook ALTER COLUMN id SET DEFAULT nextval('public.webhook_id_seq'::regclass);


--
-- Name: update_week_review id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.update_week_review ALTER COLUMN id SET DEFAULT nextval('public.sync_week_review_id_seq'::regclass);


--
-- Name: user id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public."user" ALTER COLUMN id SET DEFAULT nextval('public.user_id_seq'::regclass);


--
-- Name: user_setting id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.user_setting ALTER COLUMN id SET DEFAULT nextval('public.user_setting_id_seq'::regclass);


--
-- Name: weekly_plan id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.weekly_plan ALTER COLUMN id SET DEFAULT nextval('public.weekly_plan_id_seq'::regclass);


--
-- Name: weekly_plan_goal id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.weekly_plan_goal ALTER COLUMN id SET DEFAULT nextval('public.weekly_plan_goal_id_seq'::regclass);


--
-- Name: working_agreement id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.working_agreement ALTER COLUMN id SET DEFAULT nextval('public.working_agreement_id_seq'::regclass);


--
-- Name: working_agreement_ack id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.working_agreement_ack ALTER COLUMN id SET DEFAULT nextval('public.working_agreement_ack_id_seq'::regclass);


--
-- Name: user_setting _user_setting_uc; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.user_setting
    ADD CONSTRAINT _user_setting_uc UNIQUE (user_id, key);


--
-- Name: accounting_account accounting_account_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.accounting_account
    ADD CONSTRAINT accounting_account_pkey PRIMARY KEY (id);


--
-- Name: accounting_ledger accounting_ledger_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.accounting_ledger
    ADD CONSTRAINT accounting_ledger_pkey PRIMARY KEY (id);


--
-- Name: action_item_log action_item_log_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.action_item_log
    ADD CONSTRAINT action_item_log_pkey PRIMARY KEY (id);


--
-- Name: action_item action_item_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.action_item
    ADD CONSTRAINT action_item_pkey PRIMARY KEY (id);


--
-- Name: action_item_watcher action_item_watcher_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.action_item_watcher
    ADD CONSTRAINT action_item_watcher_pkey PRIMARY KEY (action_item_id, watcher_id);


--
-- Name: activity_log activity_log_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.activity_log
    ADD CONSTRAINT activity_log_pkey PRIMARY KEY (id);


--
-- Name: ai_pending_action ai_pending_action_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.ai_pending_action
    ADD CONSTRAINT ai_pending_action_pkey PRIMARY KEY (id);


--
-- Name: alembic_version alembic_version_pkc; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.alembic_version
    ADD CONSTRAINT alembic_version_pkc PRIMARY KEY (version_num);


--
-- Name: application_activity application_activity_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.application_activity
    ADD CONSTRAINT application_activity_pkey PRIMARY KEY (id);


--
-- Name: application application_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.application
    ADD CONSTRAINT application_pkey PRIMARY KEY (id);


--
-- Name: attachment_link attachment_link_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.attachment_link
    ADD CONSTRAINT attachment_link_pkey PRIMARY KEY (id);


--
-- Name: attachment attachment_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.attachment
    ADD CONSTRAINT attachment_pkey PRIMARY KEY (id);


--
-- Name: attachment attachment_uuid_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.attachment
    ADD CONSTRAINT attachment_uuid_key UNIQUE (uuid);


--
-- Name: audit_log audit_log_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.audit_log
    ADD CONSTRAINT audit_log_pkey PRIMARY KEY (id);


--
-- Name: auth_settings auth_settings_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.auth_settings
    ADD CONSTRAINT auth_settings_pkey PRIMARY KEY (id);


--
-- Name: billing_plan billing_plan_code_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.billing_plan
    ADD CONSTRAINT billing_plan_code_key UNIQUE (code);


--
-- Name: billing_plan billing_plan_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.billing_plan
    ADD CONSTRAINT billing_plan_pkey PRIMARY KEY (id);


--
-- Name: billing_subscription billing_subscription_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.billing_subscription
    ADD CONSTRAINT billing_subscription_pkey PRIMARY KEY (id);


--
-- Name: billing_subscription billing_subscription_stripe_subscription_id_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.billing_subscription
    ADD CONSTRAINT billing_subscription_stripe_subscription_id_key UNIQUE (stripe_subscription_id);


--
-- Name: organization business_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.organization
    ADD CONSTRAINT business_pkey PRIMARY KEY (id);


--
-- Name: organization business_slug_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.organization
    ADD CONSTRAINT business_slug_key UNIQUE (slug);


--
-- Name: candidate candidate_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.candidate
    ADD CONSTRAINT candidate_pkey PRIMARY KEY (id);


--
-- Name: canned_action canned_action_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.canned_action
    ADD CONSTRAINT canned_action_pkey PRIMARY KEY (id);


--
-- Name: update_channel channel_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.update_channel
    ADD CONSTRAINT channel_pkey PRIMARY KEY (id);


--
-- Name: clock_punch_adjustment clock_punch_adjustment_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.clock_punch_adjustment
    ADD CONSTRAINT clock_punch_adjustment_pkey PRIMARY KEY (id);


--
-- Name: clock_punch clock_punch_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.clock_punch
    ADD CONSTRAINT clock_punch_pkey PRIMARY KEY (id);


--
-- Name: event company_event_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.event
    ADD CONSTRAINT company_event_pkey PRIMARY KEY (id);


--
-- Name: update_nudge_log connect_nudge_log_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.update_nudge_log
    ADD CONSTRAINT connect_nudge_log_pkey PRIMARY KEY (id);


--
-- Name: update_post connect_post_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.update_post
    ADD CONSTRAINT connect_post_pkey PRIMARY KEY (id);


--
-- Name: update_post_reaction connect_post_reaction_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.update_post_reaction
    ADD CONSTRAINT connect_post_reaction_pkey PRIMARY KEY (id);


--
-- Name: update_template connect_template_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.update_template
    ADD CONSTRAINT connect_template_pkey PRIMARY KEY (id);


--
-- Name: contact contact_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.contact
    ADD CONSTRAINT contact_pkey PRIMARY KEY (id);


--
-- Name: update_follow content_follow_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.update_follow
    ADD CONSTRAINT content_follow_pkey PRIMARY KEY (id);


--
-- Name: device_token device_token_device_id_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.device_token
    ADD CONSTRAINT device_token_device_id_key UNIQUE (device_id);


--
-- Name: device_token device_token_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.device_token
    ADD CONSTRAINT device_token_pkey PRIMARY KEY (id);


--
-- Name: dm direct_message_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.dm
    ADD CONSTRAINT direct_message_pkey PRIMARY KEY (id);


--
-- Name: dm_ack dm_acknowledgment_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.dm_ack
    ADD CONSTRAINT dm_acknowledgment_pkey PRIMARY KEY (id);


--
-- Name: dm_reaction dm_reaction_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.dm_reaction
    ADD CONSTRAINT dm_reaction_pkey PRIMARY KEY (id);


--
-- Name: dm_thread dm_thread_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.dm_thread
    ADD CONSTRAINT dm_thread_pkey PRIMARY KEY (id);


--
-- Name: document document_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.document
    ADD CONSTRAINT document_pkey PRIMARY KEY (id);


--
-- Name: document document_uuid_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.document
    ADD CONSTRAINT document_uuid_key UNIQUE (uuid);


--
-- Name: drive_connection drive_connection_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.drive_connection
    ADD CONSTRAINT drive_connection_pkey PRIMARY KEY (id);


--
-- Name: expense expense_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.expense
    ADD CONSTRAINT expense_pkey PRIMARY KEY (id);


--
-- Name: folder folder_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.folder
    ADD CONSTRAINT folder_pkey PRIMARY KEY (id);


--
-- Name: interview interview_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.interview
    ADD CONSTRAINT interview_pkey PRIMARY KEY (id);


--
-- Name: job_posting job_posting_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.job_posting
    ADD CONSTRAINT job_posting_pkey PRIMARY KEY (id);


--
-- Name: kb_article kb_article_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.kb_article
    ADD CONSTRAINT kb_article_pkey PRIMARY KEY (id);


--
-- Name: kb_category kb_category_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.kb_category
    ADD CONSTRAINT kb_category_pkey PRIMARY KEY (id);


--
-- Name: kb_feedback kb_feedback_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.kb_feedback
    ADD CONSTRAINT kb_feedback_pkey PRIMARY KEY (id);


--
-- Name: kb_subcategory kb_subcategory_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.kb_subcategory
    ADD CONSTRAINT kb_subcategory_pkey PRIMARY KEY (id);


--
-- Name: leave_request leave_request_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.leave_request
    ADD CONSTRAINT leave_request_pkey PRIMARY KEY (id);


--
-- Name: log_entry log_entry_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.log_entry
    ADD CONSTRAINT log_entry_pkey PRIMARY KEY (id);


--
-- Name: note note_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.note
    ADD CONSTRAINT note_pkey PRIMARY KEY (id);


--
-- Name: oauth_connection oauth_connection_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.oauth_connection
    ADD CONSTRAINT oauth_connection_pkey PRIMARY KEY (id);


--
-- Name: offboarding_assignment offboarding_assignment_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.offboarding_assignment
    ADD CONSTRAINT offboarding_assignment_pkey PRIMARY KEY (id);


--
-- Name: offboarding_task offboarding_task_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.offboarding_task
    ADD CONSTRAINT offboarding_task_pkey PRIMARY KEY (id);


--
-- Name: onboarding_record onboarding_record_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.onboarding_record
    ADD CONSTRAINT onboarding_record_pkey PRIMARY KEY (id);


--
-- Name: onboarding_record onboarding_record_token_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.onboarding_record
    ADD CONSTRAINT onboarding_record_token_key UNIQUE (token);


--
-- Name: onboarding_task onboarding_task_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.onboarding_task
    ADD CONSTRAINT onboarding_task_pkey PRIMARY KEY (id);


--
-- Name: onboarding_task_template onboarding_task_template_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.onboarding_task_template
    ADD CONSTRAINT onboarding_task_template_pkey PRIMARY KEY (id);


--
-- Name: one_on_one_agenda_item one_on_one_agenda_item_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.one_on_one_agenda_item
    ADD CONSTRAINT one_on_one_agenda_item_pkey PRIMARY KEY (id);


--
-- Name: one_on_one_pair one_on_one_pair_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.one_on_one_pair
    ADD CONSTRAINT one_on_one_pair_pkey PRIMARY KEY (id);


--
-- Name: one_on_one_session one_on_one_session_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.one_on_one_session
    ADD CONSTRAINT one_on_one_session_pkey PRIMARY KEY (id);


--
-- Name: organization_invitation organization_invitation_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.organization_invitation
    ADD CONSTRAINT organization_invitation_pkey PRIMARY KEY (id);


--
-- Name: organization_user organization_user_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.organization_user
    ADD CONSTRAINT organization_user_pkey PRIMARY KEY (id);


--
-- Name: pending_signup pending_signup_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.pending_signup
    ADD CONSTRAINT pending_signup_pkey PRIMARY KEY (id);


--
-- Name: person_note person_note_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.person_note
    ADD CONSTRAINT person_note_pkey PRIMARY KEY (id);


--
-- Name: presence_settings presence_settings_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.presence_settings
    ADD CONSTRAINT presence_settings_pkey PRIMARY KEY (id);


--
-- Name: presence_settings presence_settings_public_board_token_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.presence_settings
    ADD CONSTRAINT presence_settings_public_board_token_key UNIQUE (public_board_token);


--
-- Name: presence_signal presence_signal_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.presence_signal
    ADD CONSTRAINT presence_signal_pkey PRIMARY KEY (id);


--
-- Name: project project_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.project
    ADD CONSTRAINT project_pkey PRIMARY KEY (id);


--
-- Name: punch_change_request punch_change_request_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.punch_change_request
    ADD CONSTRAINT punch_change_request_pkey PRIMARY KEY (id);


--
-- Name: push_subscription push_subscription_endpoint_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.push_subscription
    ADD CONSTRAINT push_subscription_endpoint_key UNIQUE (endpoint);


--
-- Name: push_subscription push_subscription_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.push_subscription
    ADD CONSTRAINT push_subscription_pkey PRIMARY KEY (id);


--
-- Name: refresh_token refresh_token_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.refresh_token
    ADD CONSTRAINT refresh_token_pkey PRIMARY KEY (id);


--
-- Name: resources_settings resources_settings_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.resources_settings
    ADD CONSTRAINT resources_settings_pkey PRIMARY KEY (id);


--
-- Name: service_location service_location_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.service_location
    ADD CONSTRAINT service_location_pkey PRIMARY KEY (id);


--
-- Name: signature_audit_log signature_audit_log_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.signature_audit_log
    ADD CONSTRAINT signature_audit_log_pkey PRIMARY KEY (id);


--
-- Name: signature_recipient signature_recipient_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.signature_recipient
    ADD CONSTRAINT signature_recipient_pkey PRIMARY KEY (id);


--
-- Name: signature_recipient signature_recipient_token_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.signature_recipient
    ADD CONSTRAINT signature_recipient_token_key UNIQUE (token);


--
-- Name: signature_request signature_request_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.signature_request
    ADD CONSTRAINT signature_request_pkey PRIMARY KEY (id);


--
-- Name: signature_request signature_request_uuid_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.signature_request
    ADD CONSTRAINT signature_request_uuid_key UNIQUE (uuid);


--
-- Name: update_area sync_area_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.update_area
    ADD CONSTRAINT sync_area_pkey PRIMARY KEY (id);


--
-- Name: update_post_ack sync_post_ack_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.update_post_ack
    ADD CONSTRAINT sync_post_ack_pkey PRIMARY KEY (id);


--
-- Name: update_week_review sync_week_review_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.update_week_review
    ADD CONSTRAINT sync_week_review_pkey PRIMARY KEY (id);


--
-- Name: system_notification system_notification_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.system_notification
    ADD CONSTRAINT system_notification_pkey PRIMARY KEY (id);


--
-- Name: tax_form_record tax_form_record_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.tax_form_record
    ADD CONSTRAINT tax_form_record_pkey PRIMARY KEY (id);


--
-- Name: teamspace_invite teamspace_invite_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.teamspace_invite
    ADD CONSTRAINT teamspace_invite_pkey PRIMARY KEY (id);


--
-- Name: teamspace teamspace_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.teamspace
    ADD CONSTRAINT teamspace_pkey PRIMARY KEY (id);


--
-- Name: teamspace_settings teamspace_settings_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.teamspace_settings
    ADD CONSTRAINT teamspace_settings_pkey PRIMARY KEY (id);


--
-- Name: teamspace teamspace_slug_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.teamspace
    ADD CONSTRAINT teamspace_slug_key UNIQUE (slug);


--
-- Name: teamspace_user teamspace_user_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.teamspace_user
    ADD CONSTRAINT teamspace_user_pkey PRIMARY KEY (id);


--
-- Name: time_entry time_entry_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.time_entry
    ADD CONSTRAINT time_entry_pkey PRIMARY KEY (id);


--
-- Name: timesheet_notification_recipients timesheet_notification_recipients_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.timesheet_notification_recipients
    ADD CONSTRAINT timesheet_notification_recipients_pkey PRIMARY KEY (settings_id, user_id);


--
-- Name: application unique_application; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.application
    ADD CONSTRAINT unique_application UNIQUE (job_posting_id, candidate_id);


--
-- Name: dm_reaction unique_dm_member_message_emoji; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.dm_reaction
    ADD CONSTRAINT unique_dm_member_message_emoji UNIQUE (message_id, member_id, emoji);


--
-- Name: dm_thread unique_dm_thread; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.dm_thread
    ADD CONSTRAINT unique_dm_thread UNIQUE (member1_id, member2_id);


--
-- Name: update_channel_read_state update_channel_read_state_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.update_channel_read_state
    ADD CONSTRAINT update_channel_read_state_pkey PRIMARY KEY (id);


--
-- Name: accounting_account uq_accounting_account_code_teamspace; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.accounting_account
    ADD CONSTRAINT uq_accounting_account_code_teamspace UNIQUE (code, teamspace_id);


--
-- Name: working_agreement_ack uq_agreement_member; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.working_agreement_ack
    ADD CONSTRAINT uq_agreement_member UNIQUE (agreement_id, member_id);


--
-- Name: attachment_link uq_attachment_link_entity; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.attachment_link
    ADD CONSTRAINT uq_attachment_link_entity UNIQUE (attachment_id, entity_type, entity_id);


--
-- Name: candidate uq_candidate_email_teamspace; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.candidate
    ADD CONSTRAINT uq_candidate_email_teamspace UNIQUE (email, teamspace_id);


--
-- Name: update_channel uq_channel_org_teamspace_name; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.update_channel
    ADD CONSTRAINT uq_channel_org_teamspace_name UNIQUE NULLS NOT DISTINCT (organization_id, teamspace_id, name);


--
-- Name: update_channel_read_state uq_channel_read_state; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.update_channel_read_state
    ADD CONSTRAINT uq_channel_read_state UNIQUE (member_id, channel_id, teamspace_id);


--
-- Name: update_follow uq_content_follow; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.update_follow
    ADD CONSTRAINT uq_content_follow UNIQUE (entity_type, entity_id, member_id);


--
-- Name: dm_ack uq_dm_ack; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.dm_ack
    ADD CONSTRAINT uq_dm_ack UNIQUE (message_id, member_id);


--
-- Name: document uq_document_folder_filename; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.document
    ADD CONSTRAINT uq_document_folder_filename UNIQUE (folder_id, filename);


--
-- Name: drive_connection uq_drive_connection_provider; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.drive_connection
    ADD CONSTRAINT uq_drive_connection_provider UNIQUE (provider);


--
-- Name: folder uq_folder_parent_name; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.folder
    ADD CONSTRAINT uq_folder_parent_name UNIQUE (parent_id, name);


--
-- Name: kb_article uq_kb_article_category_subcategory_slug; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.kb_article
    ADD CONSTRAINT uq_kb_article_category_subcategory_slug UNIQUE (category_id, subcategory_id, slug);


--
-- Name: kb_category uq_kb_category_slug_teamspace; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.kb_category
    ADD CONSTRAINT uq_kb_category_slug_teamspace UNIQUE (slug, teamspace_id);


--
-- Name: kb_subcategory uq_kb_subcategory_category_slug; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.kb_subcategory
    ADD CONSTRAINT uq_kb_subcategory_category_slug UNIQUE (category_id, slug);


--
-- Name: one_on_one_pair uq_one_on_one_pair; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.one_on_one_pair
    ADD CONSTRAINT uq_one_on_one_pair UNIQUE (lead_id, report_id);


--
-- Name: organization_user uq_organization_user; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.organization_user
    ADD CONSTRAINT uq_organization_user UNIQUE (organization_id, user_id);


--
-- Name: update_post_ack uq_post_ack; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.update_post_ack
    ADD CONSTRAINT uq_post_ack UNIQUE (post_id, member_id);


--
-- Name: update_post_reaction uq_post_reaction; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.update_post_reaction
    ADD CONSTRAINT uq_post_reaction UNIQUE (post_id, member_id, emoji);


--
-- Name: oauth_connection uq_provider_user_id; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.oauth_connection
    ADD CONSTRAINT uq_provider_user_id UNIQUE (provider, provider_user_id);


--
-- Name: update_area uq_sync_area_name; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.update_area
    ADD CONSTRAINT uq_sync_area_name UNIQUE (teamspace_id, name);


--
-- Name: teamspace_user uq_teamspace_user; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.teamspace_user
    ADD CONSTRAINT uq_teamspace_user UNIQUE (user_id, teamspace_id);


--
-- Name: teamspace_user uq_teamspace_user_employee_id; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.teamspace_user
    ADD CONSTRAINT uq_teamspace_user_employee_id UNIQUE (employee_id, teamspace_id);


--
-- Name: oauth_connection uq_user_provider; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.oauth_connection
    ADD CONSTRAINT uq_user_provider UNIQUE (user_id, provider);


--
-- Name: weekly_plan uq_weekly_plan_week; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.weekly_plan
    ADD CONSTRAINT uq_weekly_plan_week UNIQUE (teamspace_id, year, week_number);


--
-- Name: user user_email_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public."user"
    ADD CONSTRAINT user_email_key UNIQUE (email);


--
-- Name: user user_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public."user"
    ADD CONSTRAINT user_pkey PRIMARY KEY (id);


--
-- Name: user_setting user_setting_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.user_setting
    ADD CONSTRAINT user_setting_pkey PRIMARY KEY (id);


--
-- Name: update_webhook webhook_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.update_webhook
    ADD CONSTRAINT webhook_pkey PRIMARY KEY (id);


--
-- Name: weekly_plan_goal weekly_plan_goal_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.weekly_plan_goal
    ADD CONSTRAINT weekly_plan_goal_pkey PRIMARY KEY (id);


--
-- Name: weekly_plan weekly_plan_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.weekly_plan
    ADD CONSTRAINT weekly_plan_pkey PRIMARY KEY (id);


--
-- Name: working_agreement_ack working_agreement_ack_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.working_agreement_ack
    ADD CONSTRAINT working_agreement_ack_pkey PRIMARY KEY (id);


--
-- Name: working_agreement working_agreement_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.working_agreement
    ADD CONSTRAINT working_agreement_pkey PRIMARY KEY (id);


--
-- Name: idx_action_item_blocker_lookup; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_action_item_blocker_lookup ON public.action_item USING btree (teamspace_id, is_blocker, status);


--
-- Name: idx_action_item_project_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_action_item_project_id ON public.action_item USING btree (project_id);


--
-- Name: idx_dm_organization; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_dm_organization ON public.dm USING btree (organization_id);


--
-- Name: idx_dm_reaction_organization; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_dm_reaction_organization ON public.dm_reaction USING btree (organization_id);


--
-- Name: idx_dm_thread_organization; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_dm_thread_organization ON public.dm_thread USING btree (organization_id);


--
-- Name: idx_organization_user_organization; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_organization_user_organization ON public.organization_user USING btree (organization_id);


--
-- Name: idx_organization_user_user; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_organization_user_user ON public.organization_user USING btree (user_id);


--
-- Name: idx_project_archived; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_project_archived ON public.project USING btree (teamspace_id, archived_at);


--
-- Name: idx_project_status; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_project_status ON public.project USING btree (teamspace_id, status);


--
-- Name: idx_project_teamspace_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_project_teamspace_id ON public.project USING btree (teamspace_id);


--
-- Name: idx_teamspace_user_organization_user; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_teamspace_user_organization_user ON public.teamspace_user USING btree (organization_user_id);


--
-- Name: ix_accounting_account_organization_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_accounting_account_organization_id ON public.accounting_account USING btree (organization_id);


--
-- Name: ix_accounting_account_teamspace_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_accounting_account_teamspace_id ON public.accounting_account USING btree (teamspace_id);


--
-- Name: ix_accounting_ledger_entry_date; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_accounting_ledger_entry_date ON public.accounting_ledger USING btree (entry_date);


--
-- Name: ix_accounting_ledger_fiscal_year; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_accounting_ledger_fiscal_year ON public.accounting_ledger USING btree (fiscal_year);


--
-- Name: ix_accounting_ledger_organization_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_accounting_ledger_organization_id ON public.accounting_ledger USING btree (organization_id);


--
-- Name: ix_accounting_ledger_teamspace_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_accounting_ledger_teamspace_id ON public.accounting_ledger USING btree (teamspace_id);


--
-- Name: ix_action_item_assignee_open; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_action_item_assignee_open ON public.action_item USING btree (teamspace_id, assignee_id, status);


--
-- Name: ix_action_item_broadcast; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_action_item_broadcast ON public.action_item USING btree (broadcast_group_id);


--
-- Name: ix_action_item_log_item; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_action_item_log_item ON public.action_item_log USING btree (action_item_id, created_at);


--
-- Name: ix_action_item_organization_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_action_item_organization_id ON public.action_item USING btree (organization_id);


--
-- Name: ix_action_item_raised_by; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_action_item_raised_by ON public.action_item USING btree (teamspace_id, raised_by_id, status);


--
-- Name: ix_activity_log_created_at; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_activity_log_created_at ON public.activity_log USING btree (created_at);


--
-- Name: ix_activity_log_organization_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_activity_log_organization_id ON public.activity_log USING btree (organization_id);


--
-- Name: ix_activity_log_teamspace_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_activity_log_teamspace_id ON public.activity_log USING btree (teamspace_id);


--
-- Name: ix_ai_pending_action_organization_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_ai_pending_action_organization_id ON public.ai_pending_action USING btree (organization_id);


--
-- Name: ix_ai_pending_action_teamspace_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_ai_pending_action_teamspace_id ON public.ai_pending_action USING btree (teamspace_id);


--
-- Name: ix_application_activity_organization_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_application_activity_organization_id ON public.application_activity USING btree (organization_id);


--
-- Name: ix_application_activity_teamspace_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_application_activity_teamspace_id ON public.application_activity USING btree (teamspace_id);


--
-- Name: ix_application_organization_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_application_organization_id ON public.application USING btree (organization_id);


--
-- Name: ix_application_teamspace_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_application_teamspace_id ON public.application USING btree (teamspace_id);


--
-- Name: ix_attachment_link_entity; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_attachment_link_entity ON public.attachment_link USING btree (entity_type, entity_id);


--
-- Name: ix_attachment_link_organization_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_attachment_link_organization_id ON public.attachment_link USING btree (organization_id);


--
-- Name: ix_attachment_link_teamspace_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_attachment_link_teamspace_id ON public.attachment_link USING btree (teamspace_id);


--
-- Name: ix_attachment_organization_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_attachment_organization_id ON public.attachment USING btree (organization_id);


--
-- Name: ix_attachment_teamspace_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_attachment_teamspace_id ON public.attachment USING btree (teamspace_id);


--
-- Name: ix_audit_log_action; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_audit_log_action ON public.audit_log USING btree (action);


--
-- Name: ix_audit_log_actor_user_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_audit_log_actor_user_id ON public.audit_log USING btree (actor_user_id);


--
-- Name: ix_audit_log_org_created; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_audit_log_org_created ON public.audit_log USING btree (organization_id, created_at);


--
-- Name: ix_audit_log_organization_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_audit_log_organization_id ON public.audit_log USING btree (organization_id);


--
-- Name: ix_audit_log_teamspace_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_audit_log_teamspace_id ON public.audit_log USING btree (teamspace_id);


--
-- Name: ix_auth_settings_organization_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_auth_settings_organization_id ON public.auth_settings USING btree (organization_id);


--
-- Name: ix_auth_settings_teamspace_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_auth_settings_teamspace_id ON public.auth_settings USING btree (teamspace_id);


--
-- Name: ix_candidate_organization_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_candidate_organization_id ON public.candidate USING btree (organization_id);


--
-- Name: ix_candidate_teamspace_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_candidate_teamspace_id ON public.candidate USING btree (teamspace_id);


--
-- Name: ix_canned_action_organization_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_canned_action_organization_id ON public.canned_action USING btree (organization_id);


--
-- Name: ix_channel_teamspace_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_channel_teamspace_id ON public.update_channel USING btree (teamspace_id);


--
-- Name: ix_clock_punch_adjustment_adjusted_by_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_clock_punch_adjustment_adjusted_by_id ON public.clock_punch_adjustment USING btree (adjusted_by_id);


--
-- Name: ix_clock_punch_adjustment_clock_punch_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_clock_punch_adjustment_clock_punch_id ON public.clock_punch_adjustment USING btree (clock_punch_id);


--
-- Name: ix_clock_punch_adjustment_organization_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_clock_punch_adjustment_organization_id ON public.clock_punch_adjustment USING btree (organization_id);


--
-- Name: ix_clock_punch_adjustment_teamspace_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_clock_punch_adjustment_teamspace_id ON public.clock_punch_adjustment USING btree (teamspace_id);


--
-- Name: ix_clock_punch_member_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_clock_punch_member_id ON public.clock_punch USING btree (member_id);


--
-- Name: ix_clock_punch_member_time; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_clock_punch_member_time ON public.clock_punch USING btree (member_id, punch_time);


--
-- Name: ix_clock_punch_organization_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_clock_punch_organization_id ON public.clock_punch USING btree (organization_id);


--
-- Name: ix_clock_punch_teamspace_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_clock_punch_teamspace_id ON public.clock_punch USING btree (teamspace_id);


--
-- Name: ix_company_event_scheduled_date; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_company_event_scheduled_date ON public.event USING btree (scheduled_date);


--
-- Name: ix_company_event_teamspace_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_company_event_teamspace_id ON public.event USING btree (teamspace_id);


--
-- Name: ix_connect_post_expires_at; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_connect_post_expires_at ON public.update_post USING btree (teamspace_id, expires_at);


--
-- Name: ix_connect_post_member_date; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_connect_post_member_date ON public.update_post USING btree (teamspace_id, member_id, created_at DESC);


--
-- Name: ix_connect_post_reaction_post_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_connect_post_reaction_post_id ON public.update_post_reaction USING btree (post_id);


--
-- Name: ix_connect_post_reaction_teamspace_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_connect_post_reaction_teamspace_id ON public.update_post_reaction USING btree (teamspace_id);


--
-- Name: ix_connect_post_teamspace_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_connect_post_teamspace_id ON public.update_post USING btree (teamspace_id);


--
-- Name: ix_connect_post_template_date; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_connect_post_template_date ON public.update_post USING btree (teamspace_id, template_id, created_at DESC);


--
-- Name: ix_connect_post_type_date; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_connect_post_type_date ON public.update_post USING btree (teamspace_id, post_type, created_at DESC);


--
-- Name: ix_connect_template_post_type; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_connect_template_post_type ON public.update_template USING btree (post_type);


--
-- Name: ix_contact_deleted_at; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_contact_deleted_at ON public.contact USING btree (deleted_at);


--
-- Name: ix_contact_organization_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_contact_organization_id ON public.contact USING btree (organization_id);


--
-- Name: ix_contact_portal_access_token; Type: INDEX; Schema: public; Owner: -
--

CREATE UNIQUE INDEX ix_contact_portal_access_token ON public.contact USING btree (portal_access_token);


--
-- Name: ix_contact_teamspace_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_contact_teamspace_id ON public.contact USING btree (teamspace_id);


--
-- Name: ix_device_token_user_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_device_token_user_id ON public.device_token USING btree (user_id);


--
-- Name: ix_dm_ack_organization_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_dm_ack_organization_id ON public.dm_ack USING btree (organization_id);


--
-- Name: ix_dm_acknowledgment_teamspace_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_dm_acknowledgment_teamspace_id ON public.dm_ack USING btree (teamspace_id);


--
-- Name: ix_document_organization_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_document_organization_id ON public.document USING btree (organization_id) WHERE (organization_id IS NOT NULL);


--
-- Name: ix_document_teamspace_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_document_teamspace_id ON public.document USING btree (teamspace_id);


--
-- Name: ix_drive_connection_organization_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_drive_connection_organization_id ON public.drive_connection USING btree (organization_id);


--
-- Name: ix_drive_connection_teamspace_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_drive_connection_teamspace_id ON public.drive_connection USING btree (teamspace_id);


--
-- Name: ix_event_organization_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_event_organization_id ON public.event USING btree (organization_id);


--
-- Name: ix_expense_organization_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_expense_organization_id ON public.expense USING btree (organization_id);


--
-- Name: ix_expense_teamspace_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_expense_teamspace_id ON public.expense USING btree (teamspace_id);


--
-- Name: ix_folder_organization_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_folder_organization_id ON public.folder USING btree (organization_id) WHERE (organization_id IS NOT NULL);


--
-- Name: ix_folder_teamspace_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_folder_teamspace_id ON public.folder USING btree (teamspace_id);


--
-- Name: ix_interview_organization_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_interview_organization_id ON public.interview USING btree (organization_id);


--
-- Name: ix_interview_teamspace_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_interview_teamspace_id ON public.interview USING btree (teamspace_id);


--
-- Name: ix_job_posting_organization_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_job_posting_organization_id ON public.job_posting USING btree (organization_id);


--
-- Name: ix_job_posting_teamspace_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_job_posting_teamspace_id ON public.job_posting USING btree (teamspace_id);


--
-- Name: ix_kb_article_organization_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_kb_article_organization_id ON public.kb_article USING btree (organization_id);


--
-- Name: ix_kb_article_slug; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_kb_article_slug ON public.kb_article USING btree (slug);


--
-- Name: ix_kb_article_teamspace_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_kb_article_teamspace_id ON public.kb_article USING btree (teamspace_id);


--
-- Name: ix_kb_category_organization_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_kb_category_organization_id ON public.kb_category USING btree (organization_id);


--
-- Name: ix_kb_category_slug; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_kb_category_slug ON public.kb_category USING btree (slug);


--
-- Name: ix_kb_category_teamspace_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_kb_category_teamspace_id ON public.kb_category USING btree (teamspace_id);


--
-- Name: ix_kb_feedback_article_session; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_kb_feedback_article_session ON public.kb_feedback USING btree (article_id, session_id);


--
-- Name: ix_kb_feedback_organization_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_kb_feedback_organization_id ON public.kb_feedback USING btree (organization_id);


--
-- Name: ix_kb_feedback_teamspace_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_kb_feedback_teamspace_id ON public.kb_feedback USING btree (teamspace_id);


--
-- Name: ix_kb_subcategory_organization_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_kb_subcategory_organization_id ON public.kb_subcategory USING btree (organization_id);


--
-- Name: ix_kb_subcategory_slug; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_kb_subcategory_slug ON public.kb_subcategory USING btree (slug);


--
-- Name: ix_kb_subcategory_teamspace_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_kb_subcategory_teamspace_id ON public.kb_subcategory USING btree (teamspace_id);


--
-- Name: ix_leave_request_member_dates; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_leave_request_member_dates ON public.leave_request USING btree (member_id, start_date, end_date);


--
-- Name: ix_leave_request_member_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_leave_request_member_id ON public.leave_request USING btree (member_id);


--
-- Name: ix_leave_request_organization_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_leave_request_organization_id ON public.leave_request USING btree (organization_id);


--
-- Name: ix_leave_request_status; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_leave_request_status ON public.leave_request USING btree (status);


--
-- Name: ix_leave_request_teamspace_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_leave_request_teamspace_id ON public.leave_request USING btree (teamspace_id);


--
-- Name: ix_log_entry_timestamp; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_log_entry_timestamp ON public.log_entry USING btree ("timestamp");


--
-- Name: ix_note_member_visibility; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_note_member_visibility ON public.note USING btree (teamspace_id, member_id, visibility);


--
-- Name: ix_note_organization_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_note_organization_id ON public.note USING btree (organization_id) WHERE (organization_id IS NOT NULL);


--
-- Name: ix_note_teamspace_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_note_teamspace_id ON public.note USING btree (teamspace_id);


--
-- Name: ix_nudge_log_lookup; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_nudge_log_lookup ON public.update_nudge_log USING btree (teamspace_id, template_id, user_id, nudged_at);


--
-- Name: ix_oauth_connection_organization_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_oauth_connection_organization_id ON public.oauth_connection USING btree (organization_id);


--
-- Name: ix_oauth_connection_teamspace_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_oauth_connection_teamspace_id ON public.oauth_connection USING btree (teamspace_id);


--
-- Name: ix_oauth_provider; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_oauth_provider ON public.oauth_connection USING btree (provider);


--
-- Name: ix_offboarding_assignment_organization_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_offboarding_assignment_organization_id ON public.offboarding_assignment USING btree (organization_id);


--
-- Name: ix_offboarding_assignment_teamspace_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_offboarding_assignment_teamspace_id ON public.offboarding_assignment USING btree (teamspace_id);


--
-- Name: ix_offboarding_task_organization_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_offboarding_task_organization_id ON public.offboarding_task USING btree (organization_id);


--
-- Name: ix_offboarding_task_teamspace_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_offboarding_task_teamspace_id ON public.offboarding_task USING btree (teamspace_id);


--
-- Name: ix_onboarding_record_organization_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_onboarding_record_organization_id ON public.onboarding_record USING btree (organization_id);


--
-- Name: ix_onboarding_record_teamspace_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_onboarding_record_teamspace_id ON public.onboarding_record USING btree (teamspace_id);


--
-- Name: ix_onboarding_task_organization_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_onboarding_task_organization_id ON public.onboarding_task USING btree (organization_id);


--
-- Name: ix_onboarding_task_teamspace_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_onboarding_task_teamspace_id ON public.onboarding_task USING btree (teamspace_id);


--
-- Name: ix_onboarding_task_template_organization_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_onboarding_task_template_organization_id ON public.onboarding_task_template USING btree (organization_id);


--
-- Name: ix_onboarding_task_template_teamspace_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_onboarding_task_template_teamspace_id ON public.onboarding_task_template USING btree (teamspace_id);


--
-- Name: ix_one_on_one_agenda_item_organization_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_one_on_one_agenda_item_organization_id ON public.one_on_one_agenda_item USING btree (organization_id);


--
-- Name: ix_one_on_one_agenda_item_pair; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_one_on_one_agenda_item_pair ON public.one_on_one_agenda_item USING btree (pair_id);


--
-- Name: ix_one_on_one_pair_lead; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_one_on_one_pair_lead ON public.one_on_one_pair USING btree (lead_id);


--
-- Name: ix_one_on_one_pair_organization_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_one_on_one_pair_organization_id ON public.one_on_one_pair USING btree (organization_id);


--
-- Name: ix_one_on_one_pair_report; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_one_on_one_pair_report ON public.one_on_one_pair USING btree (report_id);


--
-- Name: ix_one_on_one_session_organization_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_one_on_one_session_organization_id ON public.one_on_one_session USING btree (organization_id);


--
-- Name: ix_one_on_one_session_pair; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_one_on_one_session_pair ON public.one_on_one_session USING btree (pair_id);


--
-- Name: ix_org_invitation_email_accepted; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_org_invitation_email_accepted ON public.organization_invitation USING btree (email, accepted_at);


--
-- Name: ix_organization_claimed_domain; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_organization_claimed_domain ON public.organization USING btree (claimed_domain);


--
-- Name: ix_organization_invitation_organization_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_organization_invitation_organization_id ON public.organization_invitation USING btree (organization_id);


--
-- Name: ix_organization_invitation_token; Type: INDEX; Schema: public; Owner: -
--

CREATE UNIQUE INDEX ix_organization_invitation_token ON public.organization_invitation USING btree (token);


--
-- Name: ix_pending_signup_email; Type: INDEX; Schema: public; Owner: -
--

CREATE UNIQUE INDEX ix_pending_signup_email ON public.pending_signup USING btree (email);


--
-- Name: ix_pending_signup_token; Type: INDEX; Schema: public; Owner: -
--

CREATE UNIQUE INDEX ix_pending_signup_token ON public.pending_signup USING btree (token);


--
-- Name: ix_person_note_deleted_at; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_person_note_deleted_at ON public.person_note USING btree (deleted_at);


--
-- Name: ix_person_note_member_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_person_note_member_id ON public.person_note USING btree (member_id);


--
-- Name: ix_person_note_organization_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_person_note_organization_id ON public.person_note USING btree (organization_id);


--
-- Name: ix_person_note_teamspace_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_person_note_teamspace_id ON public.person_note USING btree (teamspace_id);


--
-- Name: ix_presence_settings_organization_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_presence_settings_organization_id ON public.presence_settings USING btree (organization_id);


--
-- Name: ix_presence_settings_teamspace_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_presence_settings_teamspace_id ON public.presence_settings USING btree (teamspace_id);


--
-- Name: ix_presence_signal_member_template; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_presence_signal_member_template ON public.presence_signal USING btree (member_id, template_id, created_at);


--
-- Name: ix_presence_signal_team_template; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_presence_signal_team_template ON public.presence_signal USING btree (teamspace_id, template_id, created_at);


--
-- Name: ix_project_organization_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_project_organization_id ON public.project USING btree (organization_id);


--
-- Name: ix_punch_change_request_clock_punch_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_punch_change_request_clock_punch_id ON public.punch_change_request USING btree (clock_punch_id);


--
-- Name: ix_punch_change_request_member_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_punch_change_request_member_id ON public.punch_change_request USING btree (member_id);


--
-- Name: ix_punch_change_request_organization_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_punch_change_request_organization_id ON public.punch_change_request USING btree (organization_id);


--
-- Name: ix_punch_change_request_status; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_punch_change_request_status ON public.punch_change_request USING btree (status);


--
-- Name: ix_punch_change_request_teamspace_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_punch_change_request_teamspace_id ON public.punch_change_request USING btree (teamspace_id);


--
-- Name: ix_push_subscription_organization_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_push_subscription_organization_id ON public.push_subscription USING btree (organization_id);


--
-- Name: ix_push_subscription_teamspace_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_push_subscription_teamspace_id ON public.push_subscription USING btree (teamspace_id);


--
-- Name: ix_refresh_token_token_hash; Type: INDEX; Schema: public; Owner: -
--

CREATE UNIQUE INDEX ix_refresh_token_token_hash ON public.refresh_token USING btree (token_hash);


--
-- Name: ix_refresh_token_user_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_refresh_token_user_id ON public.refresh_token USING btree (user_id);


--
-- Name: ix_resources_settings_organization_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_resources_settings_organization_id ON public.resources_settings USING btree (organization_id);


--
-- Name: ix_resources_settings_teamspace_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_resources_settings_teamspace_id ON public.resources_settings USING btree (teamspace_id);


--
-- Name: ix_service_location_contact_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_service_location_contact_id ON public.service_location USING btree (contact_id);


--
-- Name: ix_service_location_organization_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_service_location_organization_id ON public.service_location USING btree (organization_id);


--
-- Name: ix_service_location_teamspace_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_service_location_teamspace_id ON public.service_location USING btree (teamspace_id);


--
-- Name: ix_signature_audit_log_organization_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_signature_audit_log_organization_id ON public.signature_audit_log USING btree (organization_id);


--
-- Name: ix_signature_audit_log_teamspace_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_signature_audit_log_teamspace_id ON public.signature_audit_log USING btree (teamspace_id);


--
-- Name: ix_signature_recipient_organization_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_signature_recipient_organization_id ON public.signature_recipient USING btree (organization_id);


--
-- Name: ix_signature_recipient_teamspace_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_signature_recipient_teamspace_id ON public.signature_recipient USING btree (teamspace_id);


--
-- Name: ix_signature_request_organization_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_signature_request_organization_id ON public.signature_request USING btree (organization_id);


--
-- Name: ix_signature_request_teamspace_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_signature_request_teamspace_id ON public.signature_request USING btree (teamspace_id);


--
-- Name: ix_sync_area_teamspace_active; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_sync_area_teamspace_active ON public.update_area USING btree (teamspace_id, is_active);


--
-- Name: ix_sync_post_ack_teamspace_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_sync_post_ack_teamspace_id ON public.update_post_ack USING btree (teamspace_id);


--
-- Name: ix_sync_week_review_week; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_sync_week_review_week ON public.update_week_review USING btree (teamspace_id, week_start);


--
-- Name: ix_system_notification_organization_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_system_notification_organization_id ON public.system_notification USING btree (organization_id);


--
-- Name: ix_system_notification_teamspace_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_system_notification_teamspace_id ON public.system_notification USING btree (teamspace_id);


--
-- Name: ix_tax_form_record_organization_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_tax_form_record_organization_id ON public.tax_form_record USING btree (organization_id);


--
-- Name: ix_tax_form_record_teamspace_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_tax_form_record_teamspace_id ON public.tax_form_record USING btree (teamspace_id);


--
-- Name: ix_teamspace_invite_email; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_teamspace_invite_email ON public.teamspace_invite USING btree (email);


--
-- Name: ix_teamspace_invite_organization_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_teamspace_invite_organization_id ON public.teamspace_invite USING btree (organization_id);


--
-- Name: ix_teamspace_invite_teamspace_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_teamspace_invite_teamspace_id ON public.teamspace_invite USING btree (teamspace_id);


--
-- Name: ix_teamspace_invite_token; Type: INDEX; Schema: public; Owner: -
--

CREATE UNIQUE INDEX ix_teamspace_invite_token ON public.teamspace_invite USING btree (token);


--
-- Name: ix_teamspace_settings_organization_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_teamspace_settings_organization_id ON public.teamspace_settings USING btree (organization_id);


--
-- Name: ix_teamspace_settings_teamspace_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_teamspace_settings_teamspace_id ON public.teamspace_settings USING btree (teamspace_id);


--
-- Name: ix_teamspace_user_deleted_at; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_teamspace_user_deleted_at ON public.teamspace_user USING btree (deleted_at);


--
-- Name: ix_teamspace_user_organization_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_teamspace_user_organization_id ON public.teamspace_user USING btree (organization_id);


--
-- Name: ix_teamspace_user_teamspace_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_teamspace_user_teamspace_id ON public.teamspace_user USING btree (teamspace_id);


--
-- Name: ix_time_entry_job_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_time_entry_job_id ON public.time_entry USING btree (job_id);


--
-- Name: ix_time_entry_member_date; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_time_entry_member_date ON public.time_entry USING btree (member_id, date);


--
-- Name: ix_time_entry_member_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_time_entry_member_id ON public.time_entry USING btree (member_id);


--
-- Name: ix_time_entry_organization_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_time_entry_organization_id ON public.time_entry USING btree (organization_id);


--
-- Name: ix_time_entry_status; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_time_entry_status ON public.time_entry USING btree (status);


--
-- Name: ix_time_entry_teamspace_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_time_entry_teamspace_id ON public.time_entry USING btree (teamspace_id);


--
-- Name: ix_update_area_organization_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_update_area_organization_id ON public.update_area USING btree (organization_id);


--
-- Name: ix_update_channel_organization_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_update_channel_organization_id ON public.update_channel USING btree (organization_id);


--
-- Name: ix_update_channel_project_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_update_channel_project_id ON public.update_channel USING btree (project_id);


--
-- Name: ix_update_channel_read_state_organization_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_update_channel_read_state_organization_id ON public.update_channel_read_state USING btree (organization_id);


--
-- Name: ix_update_channel_read_state_teamspace_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_update_channel_read_state_teamspace_id ON public.update_channel_read_state USING btree (teamspace_id);


--
-- Name: ix_update_follow_organization_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_update_follow_organization_id ON public.update_follow USING btree (organization_id);


--
-- Name: ix_update_nudge_log_organization_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_update_nudge_log_organization_id ON public.update_nudge_log USING btree (organization_id);


--
-- Name: ix_update_post_ack_organization_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_update_post_ack_organization_id ON public.update_post_ack USING btree (organization_id);


--
-- Name: ix_update_post_channel_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_update_post_channel_id ON public.update_post USING btree (channel_id);


--
-- Name: ix_update_post_channel_thread; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_update_post_channel_thread ON public.update_post USING btree (channel_id, parent_id);


--
-- Name: ix_update_post_is_win; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_update_post_is_win ON public.update_post USING btree (is_win) WHERE (is_win = true);


--
-- Name: ix_update_post_last_reply_at; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_update_post_last_reply_at ON public.update_post USING btree (last_reply_at);


--
-- Name: ix_update_post_organization_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_update_post_organization_id ON public.update_post USING btree (organization_id);


--
-- Name: ix_update_post_parent_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_update_post_parent_id ON public.update_post USING btree (parent_id);


--
-- Name: ix_update_post_reaction_organization_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_update_post_reaction_organization_id ON public.update_post_reaction USING btree (organization_id);


--
-- Name: ix_update_webhook_organization_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_update_webhook_organization_id ON public.update_webhook USING btree (organization_id);


--
-- Name: ix_update_week_review_organization_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_update_week_review_organization_id ON public.update_week_review USING btree (organization_id);


--
-- Name: ix_user_magic_link_token; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_user_magic_link_token ON public."user" USING btree (magic_link_token);


--
-- Name: ix_user_password_reset_token; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_user_password_reset_token ON public."user" USING btree (password_reset_token);


--
-- Name: ix_user_phone_number; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_user_phone_number ON public."user" USING btree (phone_number);


--
-- Name: ix_user_setting_organization_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_user_setting_organization_id ON public.user_setting USING btree (organization_id);


--
-- Name: ix_user_setting_teamspace_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_user_setting_teamspace_id ON public.user_setting USING btree (teamspace_id);


--
-- Name: ix_webhook_teamspace_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_webhook_teamspace_id ON public.update_webhook USING btree (teamspace_id);


--
-- Name: ix_webhook_token; Type: INDEX; Schema: public; Owner: -
--

CREATE UNIQUE INDEX ix_webhook_token ON public.update_webhook USING btree (token);


--
-- Name: ix_weekly_plan_goal_plan; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_weekly_plan_goal_plan ON public.weekly_plan_goal USING btree (plan_id);


--
-- Name: ix_weekly_plan_lookup; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_weekly_plan_lookup ON public.weekly_plan USING btree (teamspace_id, year, week_number);


--
-- Name: ix_weekly_plan_organization_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_weekly_plan_organization_id ON public.weekly_plan USING btree (organization_id);


--
-- Name: ix_working_agreement_ack_agreement; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_working_agreement_ack_agreement ON public.working_agreement_ack USING btree (agreement_id);


--
-- Name: ix_working_agreement_ack_member; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_working_agreement_ack_member ON public.working_agreement_ack USING btree (member_id);


--
-- Name: ix_working_agreement_ack_organization_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_working_agreement_ack_organization_id ON public.working_agreement_ack USING btree (organization_id);


--
-- Name: ix_working_agreement_organization_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_working_agreement_organization_id ON public.working_agreement USING btree (organization_id);


--
-- Name: accounting_account accounting_account_organization_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.accounting_account
    ADD CONSTRAINT accounting_account_organization_id_fkey FOREIGN KEY (organization_id) REFERENCES public.organization(id) ON DELETE CASCADE;


--
-- Name: accounting_account accounting_account_parent_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.accounting_account
    ADD CONSTRAINT accounting_account_parent_id_fkey FOREIGN KEY (parent_id) REFERENCES public.accounting_account(id);


--
-- Name: accounting_account accounting_account_teamspace_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.accounting_account
    ADD CONSTRAINT accounting_account_teamspace_id_fkey FOREIGN KEY (teamspace_id) REFERENCES public.teamspace(id) ON DELETE CASCADE;


--
-- Name: accounting_ledger accounting_ledger_account_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.accounting_ledger
    ADD CONSTRAINT accounting_ledger_account_id_fkey FOREIGN KEY (account_id) REFERENCES public.accounting_account(id);


--
-- Name: accounting_ledger accounting_ledger_created_by_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.accounting_ledger
    ADD CONSTRAINT accounting_ledger_created_by_id_fkey FOREIGN KEY (created_by_id) REFERENCES public."user"(id);


--
-- Name: accounting_ledger accounting_ledger_organization_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.accounting_ledger
    ADD CONSTRAINT accounting_ledger_organization_id_fkey FOREIGN KEY (organization_id) REFERENCES public.organization(id) ON DELETE CASCADE;


--
-- Name: accounting_ledger accounting_ledger_teamspace_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.accounting_ledger
    ADD CONSTRAINT accounting_ledger_teamspace_id_fkey FOREIGN KEY (teamspace_id) REFERENCES public.teamspace(id) ON DELETE CASCADE;


--
-- Name: action_item action_item_area_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.action_item
    ADD CONSTRAINT action_item_area_id_fkey FOREIGN KEY (area_id) REFERENCES public.update_area(id) ON DELETE SET NULL;


--
-- Name: action_item action_item_assignee_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.action_item
    ADD CONSTRAINT action_item_assignee_id_fkey FOREIGN KEY (assignee_id) REFERENCES public.teamspace_user(id);


--
-- Name: action_item_log action_item_log_action_item_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.action_item_log
    ADD CONSTRAINT action_item_log_action_item_id_fkey FOREIGN KEY (action_item_id) REFERENCES public.action_item(id) ON DELETE CASCADE;


--
-- Name: action_item_log action_item_log_actor_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.action_item_log
    ADD CONSTRAINT action_item_log_actor_id_fkey FOREIGN KEY (actor_id) REFERENCES public.teamspace_user(id);


--
-- Name: action_item action_item_organization_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.action_item
    ADD CONSTRAINT action_item_organization_id_fkey FOREIGN KEY (organization_id) REFERENCES public.organization(id) ON DELETE CASCADE;


--
-- Name: action_item action_item_project_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.action_item
    ADD CONSTRAINT action_item_project_id_fkey FOREIGN KEY (project_id) REFERENCES public.project(id) ON DELETE SET NULL;


--
-- Name: action_item action_item_raised_by_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.action_item
    ADD CONSTRAINT action_item_raised_by_id_fkey FOREIGN KEY (raised_by_id) REFERENCES public.teamspace_user(id);


--
-- Name: action_item action_item_resolved_by_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.action_item
    ADD CONSTRAINT action_item_resolved_by_id_fkey FOREIGN KEY (resolved_by_id) REFERENCES public.teamspace_user(id);


--
-- Name: action_item action_item_teamspace_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.action_item
    ADD CONSTRAINT action_item_teamspace_id_fkey FOREIGN KEY (teamspace_id) REFERENCES public.teamspace(id) ON DELETE CASCADE;


--
-- Name: action_item_watcher action_item_watcher_action_item_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.action_item_watcher
    ADD CONSTRAINT action_item_watcher_action_item_id_fkey FOREIGN KEY (action_item_id) REFERENCES public.action_item(id) ON DELETE CASCADE;


--
-- Name: action_item_watcher action_item_watcher_watcher_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.action_item_watcher
    ADD CONSTRAINT action_item_watcher_watcher_id_fkey FOREIGN KEY (watcher_id) REFERENCES public.teamspace_user(id) ON DELETE CASCADE;


--
-- Name: activity_log activity_log_member_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.activity_log
    ADD CONSTRAINT activity_log_member_id_fkey FOREIGN KEY (member_id) REFERENCES public.teamspace_user(id) ON DELETE SET NULL;


--
-- Name: activity_log activity_log_organization_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.activity_log
    ADD CONSTRAINT activity_log_organization_id_fkey FOREIGN KEY (organization_id) REFERENCES public.organization(id) ON DELETE CASCADE;


--
-- Name: activity_log activity_log_teamspace_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.activity_log
    ADD CONSTRAINT activity_log_teamspace_id_fkey FOREIGN KEY (teamspace_id) REFERENCES public.teamspace(id) ON DELETE CASCADE;


--
-- Name: ai_pending_action ai_pending_action_channel_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.ai_pending_action
    ADD CONSTRAINT ai_pending_action_channel_id_fkey FOREIGN KEY (channel_id) REFERENCES public.update_channel(id);


--
-- Name: ai_pending_action ai_pending_action_created_by_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.ai_pending_action
    ADD CONSTRAINT ai_pending_action_created_by_id_fkey FOREIGN KEY (created_by_id) REFERENCES public."user"(id);


--
-- Name: ai_pending_action ai_pending_action_organization_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.ai_pending_action
    ADD CONSTRAINT ai_pending_action_organization_id_fkey FOREIGN KEY (organization_id) REFERENCES public.organization(id) ON DELETE CASCADE;


--
-- Name: ai_pending_action ai_pending_action_teamspace_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.ai_pending_action
    ADD CONSTRAINT ai_pending_action_teamspace_id_fkey FOREIGN KEY (teamspace_id) REFERENCES public.teamspace(id) ON DELETE CASCADE;


--
-- Name: application_activity application_activity_application_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.application_activity
    ADD CONSTRAINT application_activity_application_id_fkey FOREIGN KEY (application_id) REFERENCES public.application(id);


--
-- Name: application_activity application_activity_created_by_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.application_activity
    ADD CONSTRAINT application_activity_created_by_id_fkey FOREIGN KEY (created_by_id) REFERENCES public."user"(id);


--
-- Name: application_activity application_activity_organization_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.application_activity
    ADD CONSTRAINT application_activity_organization_id_fkey FOREIGN KEY (organization_id) REFERENCES public.organization(id) ON DELETE CASCADE;


--
-- Name: application_activity application_activity_teamspace_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.application_activity
    ADD CONSTRAINT application_activity_teamspace_id_fkey FOREIGN KEY (teamspace_id) REFERENCES public.teamspace(id) ON DELETE CASCADE;


--
-- Name: application application_candidate_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.application
    ADD CONSTRAINT application_candidate_id_fkey FOREIGN KEY (candidate_id) REFERENCES public.candidate(id);


--
-- Name: application application_created_by_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.application
    ADD CONSTRAINT application_created_by_id_fkey FOREIGN KEY (created_by_id) REFERENCES public."user"(id);


--
-- Name: application application_job_posting_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.application
    ADD CONSTRAINT application_job_posting_id_fkey FOREIGN KEY (job_posting_id) REFERENCES public.job_posting(id);


--
-- Name: application application_onboarding_record_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.application
    ADD CONSTRAINT application_onboarding_record_id_fkey FOREIGN KEY (onboarding_record_id) REFERENCES public.onboarding_record(id);


--
-- Name: application application_organization_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.application
    ADD CONSTRAINT application_organization_id_fkey FOREIGN KEY (organization_id) REFERENCES public.organization(id) ON DELETE CASCADE;


--
-- Name: application application_teamspace_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.application
    ADD CONSTRAINT application_teamspace_id_fkey FOREIGN KEY (teamspace_id) REFERENCES public.teamspace(id) ON DELETE CASCADE;


--
-- Name: application application_updated_by_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.application
    ADD CONSTRAINT application_updated_by_id_fkey FOREIGN KEY (updated_by_id) REFERENCES public."user"(id);


--
-- Name: attachment_link attachment_link_attachment_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.attachment_link
    ADD CONSTRAINT attachment_link_attachment_id_fkey FOREIGN KEY (attachment_id) REFERENCES public.attachment(id) ON DELETE CASCADE;


--
-- Name: attachment_link attachment_link_organization_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.attachment_link
    ADD CONSTRAINT attachment_link_organization_id_fkey FOREIGN KEY (organization_id) REFERENCES public.organization(id) ON DELETE CASCADE;


--
-- Name: attachment_link attachment_link_teamspace_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.attachment_link
    ADD CONSTRAINT attachment_link_teamspace_id_fkey FOREIGN KEY (teamspace_id) REFERENCES public.teamspace(id) ON DELETE CASCADE;


--
-- Name: attachment attachment_organization_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.attachment
    ADD CONSTRAINT attachment_organization_id_fkey FOREIGN KEY (organization_id) REFERENCES public.organization(id) ON DELETE CASCADE;


--
-- Name: attachment attachment_teamspace_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.attachment
    ADD CONSTRAINT attachment_teamspace_id_fkey FOREIGN KEY (teamspace_id) REFERENCES public.teamspace(id) ON DELETE CASCADE;


--
-- Name: audit_log audit_log_actor_organization_user_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.audit_log
    ADD CONSTRAINT audit_log_actor_organization_user_id_fkey FOREIGN KEY (actor_organization_user_id) REFERENCES public.organization_user(id) ON DELETE SET NULL;


--
-- Name: audit_log audit_log_actor_user_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.audit_log
    ADD CONSTRAINT audit_log_actor_user_id_fkey FOREIGN KEY (actor_user_id) REFERENCES public."user"(id) ON DELETE SET NULL;


--
-- Name: audit_log audit_log_organization_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.audit_log
    ADD CONSTRAINT audit_log_organization_id_fkey FOREIGN KEY (organization_id) REFERENCES public.organization(id) ON DELETE CASCADE;


--
-- Name: audit_log audit_log_teamspace_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.audit_log
    ADD CONSTRAINT audit_log_teamspace_id_fkey FOREIGN KEY (teamspace_id) REFERENCES public.teamspace(id) ON DELETE SET NULL;


--
-- Name: auth_settings auth_settings_organization_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.auth_settings
    ADD CONSTRAINT auth_settings_organization_id_fkey FOREIGN KEY (organization_id) REFERENCES public.organization(id) ON DELETE CASCADE;


--
-- Name: auth_settings auth_settings_teamspace_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.auth_settings
    ADD CONSTRAINT auth_settings_teamspace_id_fkey FOREIGN KEY (teamspace_id) REFERENCES public.teamspace(id) ON DELETE CASCADE;


--
-- Name: billing_subscription billing_subscription_business_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.billing_subscription
    ADD CONSTRAINT billing_subscription_business_id_fkey FOREIGN KEY (organization_id) REFERENCES public.organization(id) ON DELETE CASCADE;


--
-- Name: billing_subscription billing_subscription_plan_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.billing_subscription
    ADD CONSTRAINT billing_subscription_plan_id_fkey FOREIGN KEY (plan_id) REFERENCES public.billing_plan(id);


--
-- Name: organization business_owner_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.organization
    ADD CONSTRAINT business_owner_id_fkey FOREIGN KEY (owner_id) REFERENCES public."user"(id);


--
-- Name: candidate candidate_created_by_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.candidate
    ADD CONSTRAINT candidate_created_by_id_fkey FOREIGN KEY (created_by_id) REFERENCES public."user"(id);


--
-- Name: candidate candidate_organization_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.candidate
    ADD CONSTRAINT candidate_organization_id_fkey FOREIGN KEY (organization_id) REFERENCES public.organization(id) ON DELETE CASCADE;


--
-- Name: candidate candidate_resume_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.candidate
    ADD CONSTRAINT candidate_resume_id_fkey FOREIGN KEY (resume_id) REFERENCES public.attachment(id);


--
-- Name: candidate candidate_teamspace_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.candidate
    ADD CONSTRAINT candidate_teamspace_id_fkey FOREIGN KEY (teamspace_id) REFERENCES public.teamspace(id) ON DELETE CASCADE;


--
-- Name: candidate candidate_updated_by_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.candidate
    ADD CONSTRAINT candidate_updated_by_id_fkey FOREIGN KEY (updated_by_id) REFERENCES public."user"(id);


--
-- Name: canned_action canned_action_created_by_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.canned_action
    ADD CONSTRAINT canned_action_created_by_id_fkey FOREIGN KEY (created_by_id) REFERENCES public.teamspace_user(id);


--
-- Name: canned_action canned_action_organization_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.canned_action
    ADD CONSTRAINT canned_action_organization_id_fkey FOREIGN KEY (organization_id) REFERENCES public.organization(id) ON DELETE CASCADE;


--
-- Name: canned_action canned_action_teamspace_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.canned_action
    ADD CONSTRAINT canned_action_teamspace_id_fkey FOREIGN KEY (teamspace_id) REFERENCES public.teamspace(id);


--
-- Name: update_channel channel_created_by_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.update_channel
    ADD CONSTRAINT channel_created_by_id_fkey FOREIGN KEY (created_by_id) REFERENCES public.teamspace_user(id);


--
-- Name: update_channel channel_teamspace_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.update_channel
    ADD CONSTRAINT channel_teamspace_id_fkey FOREIGN KEY (teamspace_id) REFERENCES public.teamspace(id) ON DELETE CASCADE;


--
-- Name: clock_punch_adjustment clock_punch_adjustment_adjusted_by_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.clock_punch_adjustment
    ADD CONSTRAINT clock_punch_adjustment_adjusted_by_id_fkey FOREIGN KEY (adjusted_by_id) REFERENCES public.teamspace_user(id);


--
-- Name: clock_punch_adjustment clock_punch_adjustment_clock_punch_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.clock_punch_adjustment
    ADD CONSTRAINT clock_punch_adjustment_clock_punch_id_fkey FOREIGN KEY (clock_punch_id) REFERENCES public.clock_punch(id) ON DELETE CASCADE;


--
-- Name: clock_punch_adjustment clock_punch_adjustment_organization_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.clock_punch_adjustment
    ADD CONSTRAINT clock_punch_adjustment_organization_id_fkey FOREIGN KEY (organization_id) REFERENCES public.organization(id) ON DELETE CASCADE;


--
-- Name: clock_punch_adjustment clock_punch_adjustment_teamspace_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.clock_punch_adjustment
    ADD CONSTRAINT clock_punch_adjustment_teamspace_id_fkey FOREIGN KEY (teamspace_id) REFERENCES public.teamspace(id) ON DELETE CASCADE;


--
-- Name: clock_punch clock_punch_member_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.clock_punch
    ADD CONSTRAINT clock_punch_member_id_fkey FOREIGN KEY (member_id) REFERENCES public.teamspace_user(id) ON DELETE CASCADE;


--
-- Name: clock_punch clock_punch_organization_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.clock_punch
    ADD CONSTRAINT clock_punch_organization_id_fkey FOREIGN KEY (organization_id) REFERENCES public.organization(id) ON DELETE CASCADE;


--
-- Name: clock_punch clock_punch_teamspace_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.clock_punch
    ADD CONSTRAINT clock_punch_teamspace_id_fkey FOREIGN KEY (teamspace_id) REFERENCES public.teamspace(id) ON DELETE CASCADE;


--
-- Name: clock_punch clock_punch_time_entry_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.clock_punch
    ADD CONSTRAINT clock_punch_time_entry_id_fkey FOREIGN KEY (time_entry_id) REFERENCES public.time_entry(id) ON DELETE SET NULL;


--
-- Name: event company_event_created_by_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.event
    ADD CONSTRAINT company_event_created_by_id_fkey FOREIGN KEY (created_by_id) REFERENCES public."user"(id);


--
-- Name: event company_event_teamspace_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.event
    ADD CONSTRAINT company_event_teamspace_id_fkey FOREIGN KEY (teamspace_id) REFERENCES public.teamspace(id) ON DELETE CASCADE;


--
-- Name: event company_event_updated_by_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.event
    ADD CONSTRAINT company_event_updated_by_id_fkey FOREIGN KEY (updated_by_id) REFERENCES public."user"(id);


--
-- Name: update_nudge_log connect_nudge_log_teamspace_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.update_nudge_log
    ADD CONSTRAINT connect_nudge_log_teamspace_id_fkey FOREIGN KEY (teamspace_id) REFERENCES public.teamspace(id) ON DELETE CASCADE;


--
-- Name: update_nudge_log connect_nudge_log_template_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.update_nudge_log
    ADD CONSTRAINT connect_nudge_log_template_id_fkey FOREIGN KEY (template_id) REFERENCES public.update_template(id) ON DELETE CASCADE;


--
-- Name: update_nudge_log connect_nudge_log_user_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.update_nudge_log
    ADD CONSTRAINT connect_nudge_log_user_id_fkey FOREIGN KEY (user_id) REFERENCES public."user"(id) ON DELETE CASCADE;


--
-- Name: update_post connect_post_member_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.update_post
    ADD CONSTRAINT connect_post_member_id_fkey FOREIGN KEY (member_id) REFERENCES public.teamspace_user(id);


--
-- Name: update_post_reaction connect_post_reaction_member_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.update_post_reaction
    ADD CONSTRAINT connect_post_reaction_member_id_fkey FOREIGN KEY (member_id) REFERENCES public.teamspace_user(id);


--
-- Name: update_post_reaction connect_post_reaction_post_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.update_post_reaction
    ADD CONSTRAINT connect_post_reaction_post_id_fkey FOREIGN KEY (post_id) REFERENCES public.update_post(id) ON DELETE CASCADE;


--
-- Name: update_post_reaction connect_post_reaction_teamspace_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.update_post_reaction
    ADD CONSTRAINT connect_post_reaction_teamspace_id_fkey FOREIGN KEY (teamspace_id) REFERENCES public.teamspace(id) ON DELETE CASCADE;


--
-- Name: update_post connect_post_teamspace_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.update_post
    ADD CONSTRAINT connect_post_teamspace_id_fkey FOREIGN KEY (teamspace_id) REFERENCES public.teamspace(id) ON DELETE CASCADE;


--
-- Name: update_post connect_post_template_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.update_post
    ADD CONSTRAINT connect_post_template_id_fkey FOREIGN KEY (template_id) REFERENCES public.update_template(id);


--
-- Name: update_template connect_template_teamspace_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.update_template
    ADD CONSTRAINT connect_template_teamspace_id_fkey FOREIGN KEY (teamspace_id) REFERENCES public.teamspace(id) ON DELETE CASCADE;


--
-- Name: contact contact_created_by_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.contact
    ADD CONSTRAINT contact_created_by_id_fkey FOREIGN KEY (created_by_id) REFERENCES public."user"(id);


--
-- Name: contact contact_deleted_by_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.contact
    ADD CONSTRAINT contact_deleted_by_id_fkey FOREIGN KEY (deleted_by_id) REFERENCES public."user"(id);


--
-- Name: contact contact_organization_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.contact
    ADD CONSTRAINT contact_organization_id_fkey FOREIGN KEY (organization_id) REFERENCES public.organization(id) ON DELETE CASCADE;


--
-- Name: contact contact_teamspace_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.contact
    ADD CONSTRAINT contact_teamspace_id_fkey FOREIGN KEY (teamspace_id) REFERENCES public.teamspace(id) ON DELETE CASCADE;


--
-- Name: contact contact_updated_by_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.contact
    ADD CONSTRAINT contact_updated_by_id_fkey FOREIGN KEY (updated_by_id) REFERENCES public."user"(id);


--
-- Name: update_follow content_follow_member_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.update_follow
    ADD CONSTRAINT content_follow_member_id_fkey FOREIGN KEY (member_id) REFERENCES public.teamspace_user(id);


--
-- Name: update_follow content_follow_teamspace_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.update_follow
    ADD CONSTRAINT content_follow_teamspace_id_fkey FOREIGN KEY (teamspace_id) REFERENCES public.teamspace(id) ON DELETE CASCADE;


--
-- Name: device_token device_token_user_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.device_token
    ADD CONSTRAINT device_token_user_id_fkey FOREIGN KEY (user_id) REFERENCES public."user"(id);


--
-- Name: dm direct_message_member_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.dm
    ADD CONSTRAINT direct_message_member_id_fkey FOREIGN KEY (member_id) REFERENCES public.teamspace_user(id);


--
-- Name: dm direct_message_thread_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.dm
    ADD CONSTRAINT direct_message_thread_id_fkey FOREIGN KEY (thread_id) REFERENCES public.dm_thread(id) ON DELETE CASCADE;


--
-- Name: dm direct_message_webhook_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.dm
    ADD CONSTRAINT direct_message_webhook_id_fkey FOREIGN KEY (webhook_id) REFERENCES public.update_webhook(id) ON DELETE SET NULL;


--
-- Name: dm_ack dm_ack_organization_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.dm_ack
    ADD CONSTRAINT dm_ack_organization_id_fkey FOREIGN KEY (organization_id) REFERENCES public.organization(id) ON DELETE CASCADE;


--
-- Name: dm_ack dm_acknowledgment_member_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.dm_ack
    ADD CONSTRAINT dm_acknowledgment_member_id_fkey FOREIGN KEY (member_id) REFERENCES public.teamspace_user(id);


--
-- Name: dm_ack dm_acknowledgment_message_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.dm_ack
    ADD CONSTRAINT dm_acknowledgment_message_id_fkey FOREIGN KEY (message_id) REFERENCES public.dm(id) ON DELETE CASCADE;


--
-- Name: dm_ack dm_acknowledgment_teamspace_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.dm_ack
    ADD CONSTRAINT dm_acknowledgment_teamspace_id_fkey FOREIGN KEY (teamspace_id) REFERENCES public.teamspace(id) ON DELETE CASCADE;


--
-- Name: dm dm_organization_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.dm
    ADD CONSTRAINT dm_organization_id_fkey FOREIGN KEY (organization_id) REFERENCES public.organization(id) ON DELETE CASCADE;


--
-- Name: dm_reaction dm_reaction_member_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.dm_reaction
    ADD CONSTRAINT dm_reaction_member_id_fkey FOREIGN KEY (member_id) REFERENCES public.teamspace_user(id) ON DELETE CASCADE;


--
-- Name: dm_reaction dm_reaction_message_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.dm_reaction
    ADD CONSTRAINT dm_reaction_message_id_fkey FOREIGN KEY (message_id) REFERENCES public.dm(id) ON DELETE CASCADE;


--
-- Name: dm_reaction dm_reaction_organization_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.dm_reaction
    ADD CONSTRAINT dm_reaction_organization_id_fkey FOREIGN KEY (organization_id) REFERENCES public.organization(id) ON DELETE CASCADE;


--
-- Name: dm_thread dm_thread_member1_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.dm_thread
    ADD CONSTRAINT dm_thread_member1_id_fkey FOREIGN KEY (member1_id) REFERENCES public.teamspace_user(id);


--
-- Name: dm_thread dm_thread_member2_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.dm_thread
    ADD CONSTRAINT dm_thread_member2_id_fkey FOREIGN KEY (member2_id) REFERENCES public.teamspace_user(id);


--
-- Name: dm_thread dm_thread_organization_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.dm_thread
    ADD CONSTRAINT dm_thread_organization_id_fkey FOREIGN KEY (organization_id) REFERENCES public.organization(id) ON DELETE CASCADE;


--
-- Name: document document_created_by_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.document
    ADD CONSTRAINT document_created_by_id_fkey FOREIGN KEY (created_by_id) REFERENCES public."user"(id);


--
-- Name: document document_folder_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.document
    ADD CONSTRAINT document_folder_id_fkey FOREIGN KEY (folder_id) REFERENCES public.folder(id) ON DELETE CASCADE;


--
-- Name: document document_organization_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.document
    ADD CONSTRAINT document_organization_id_fkey FOREIGN KEY (organization_id) REFERENCES public.organization(id) ON DELETE CASCADE;


--
-- Name: document document_teamspace_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.document
    ADD CONSTRAINT document_teamspace_id_fkey FOREIGN KEY (teamspace_id) REFERENCES public.teamspace(id) ON DELETE CASCADE;


--
-- Name: document document_updated_by_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.document
    ADD CONSTRAINT document_updated_by_id_fkey FOREIGN KEY (updated_by_id) REFERENCES public."user"(id);


--
-- Name: drive_connection drive_connection_connected_by_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.drive_connection
    ADD CONSTRAINT drive_connection_connected_by_id_fkey FOREIGN KEY (connected_by_id) REFERENCES public."user"(id);


--
-- Name: drive_connection drive_connection_organization_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.drive_connection
    ADD CONSTRAINT drive_connection_organization_id_fkey FOREIGN KEY (organization_id) REFERENCES public.organization(id) ON DELETE CASCADE;


--
-- Name: drive_connection drive_connection_teamspace_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.drive_connection
    ADD CONSTRAINT drive_connection_teamspace_id_fkey FOREIGN KEY (teamspace_id) REFERENCES public.teamspace(id) ON DELETE CASCADE;


--
-- Name: event event_organization_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.event
    ADD CONSTRAINT event_organization_id_fkey FOREIGN KEY (organization_id) REFERENCES public.organization(id) ON DELETE CASCADE;


--
-- Name: expense expense_organization_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.expense
    ADD CONSTRAINT expense_organization_id_fkey FOREIGN KEY (organization_id) REFERENCES public.organization(id) ON DELETE CASCADE;


--
-- Name: expense expense_reimbursed_by_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.expense
    ADD CONSTRAINT expense_reimbursed_by_id_fkey FOREIGN KEY (reimbursed_by_id) REFERENCES public."user"(id);


--
-- Name: expense expense_reviewed_by_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.expense
    ADD CONSTRAINT expense_reviewed_by_id_fkey FOREIGN KEY (reviewed_by_id) REFERENCES public."user"(id);


--
-- Name: expense expense_submitted_by_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.expense
    ADD CONSTRAINT expense_submitted_by_id_fkey FOREIGN KEY (submitted_by_id) REFERENCES public."user"(id);


--
-- Name: expense expense_teamspace_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.expense
    ADD CONSTRAINT expense_teamspace_id_fkey FOREIGN KEY (teamspace_id) REFERENCES public.teamspace(id) ON DELETE CASCADE;


--
-- Name: update_channel fk_update_channel_project_id; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.update_channel
    ADD CONSTRAINT fk_update_channel_project_id FOREIGN KEY (project_id) REFERENCES public.project(id) ON DELETE SET NULL;


--
-- Name: update_post fk_update_post_channel_id; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.update_post
    ADD CONSTRAINT fk_update_post_channel_id FOREIGN KEY (channel_id) REFERENCES public.update_channel(id) ON DELETE SET NULL;


--
-- Name: update_post fk_update_post_parent_id; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.update_post
    ADD CONSTRAINT fk_update_post_parent_id FOREIGN KEY (parent_id) REFERENCES public.update_post(id) ON DELETE CASCADE;


--
-- Name: folder folder_created_by_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.folder
    ADD CONSTRAINT folder_created_by_id_fkey FOREIGN KEY (created_by_id) REFERENCES public."user"(id);


--
-- Name: folder folder_organization_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.folder
    ADD CONSTRAINT folder_organization_id_fkey FOREIGN KEY (organization_id) REFERENCES public.organization(id) ON DELETE CASCADE;


--
-- Name: folder folder_parent_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.folder
    ADD CONSTRAINT folder_parent_id_fkey FOREIGN KEY (parent_id) REFERENCES public.folder(id);


--
-- Name: folder folder_teamspace_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.folder
    ADD CONSTRAINT folder_teamspace_id_fkey FOREIGN KEY (teamspace_id) REFERENCES public.teamspace(id) ON DELETE CASCADE;


--
-- Name: folder folder_updated_by_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.folder
    ADD CONSTRAINT folder_updated_by_id_fkey FOREIGN KEY (updated_by_id) REFERENCES public."user"(id);


--
-- Name: interview interview_application_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.interview
    ADD CONSTRAINT interview_application_id_fkey FOREIGN KEY (application_id) REFERENCES public.application(id);


--
-- Name: interview interview_created_by_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.interview
    ADD CONSTRAINT interview_created_by_id_fkey FOREIGN KEY (created_by_id) REFERENCES public."user"(id);


--
-- Name: interview interview_interviewer_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.interview
    ADD CONSTRAINT interview_interviewer_id_fkey FOREIGN KEY (interviewer_id) REFERENCES public.teamspace_user(id);


--
-- Name: interview interview_organization_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.interview
    ADD CONSTRAINT interview_organization_id_fkey FOREIGN KEY (organization_id) REFERENCES public.organization(id) ON DELETE CASCADE;


--
-- Name: interview interview_teamspace_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.interview
    ADD CONSTRAINT interview_teamspace_id_fkey FOREIGN KEY (teamspace_id) REFERENCES public.teamspace(id) ON DELETE CASCADE;


--
-- Name: interview interview_updated_by_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.interview
    ADD CONSTRAINT interview_updated_by_id_fkey FOREIGN KEY (updated_by_id) REFERENCES public."user"(id);


--
-- Name: job_posting job_posting_created_by_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.job_posting
    ADD CONSTRAINT job_posting_created_by_id_fkey FOREIGN KEY (created_by_id) REFERENCES public."user"(id);


--
-- Name: job_posting job_posting_hiring_manager_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.job_posting
    ADD CONSTRAINT job_posting_hiring_manager_id_fkey FOREIGN KEY (hiring_manager_id) REFERENCES public.teamspace_user(id);


--
-- Name: job_posting job_posting_organization_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.job_posting
    ADD CONSTRAINT job_posting_organization_id_fkey FOREIGN KEY (organization_id) REFERENCES public.organization(id) ON DELETE CASCADE;


--
-- Name: job_posting job_posting_teamspace_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.job_posting
    ADD CONSTRAINT job_posting_teamspace_id_fkey FOREIGN KEY (teamspace_id) REFERENCES public.teamspace(id) ON DELETE CASCADE;


--
-- Name: job_posting job_posting_updated_by_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.job_posting
    ADD CONSTRAINT job_posting_updated_by_id_fkey FOREIGN KEY (updated_by_id) REFERENCES public."user"(id);


--
-- Name: kb_article kb_article_category_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.kb_article
    ADD CONSTRAINT kb_article_category_id_fkey FOREIGN KEY (category_id) REFERENCES public.kb_category(id);


--
-- Name: kb_article kb_article_created_by_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.kb_article
    ADD CONSTRAINT kb_article_created_by_id_fkey FOREIGN KEY (created_by_id) REFERENCES public."user"(id);


--
-- Name: kb_article kb_article_organization_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.kb_article
    ADD CONSTRAINT kb_article_organization_id_fkey FOREIGN KEY (organization_id) REFERENCES public.organization(id) ON DELETE CASCADE;


--
-- Name: kb_article kb_article_subcategory_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.kb_article
    ADD CONSTRAINT kb_article_subcategory_id_fkey FOREIGN KEY (subcategory_id) REFERENCES public.kb_subcategory(id) ON DELETE SET NULL;


--
-- Name: kb_article kb_article_teamspace_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.kb_article
    ADD CONSTRAINT kb_article_teamspace_id_fkey FOREIGN KEY (teamspace_id) REFERENCES public.teamspace(id) ON DELETE CASCADE;


--
-- Name: kb_article kb_article_updated_by_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.kb_article
    ADD CONSTRAINT kb_article_updated_by_id_fkey FOREIGN KEY (updated_by_id) REFERENCES public."user"(id);


--
-- Name: kb_category kb_category_created_by_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.kb_category
    ADD CONSTRAINT kb_category_created_by_id_fkey FOREIGN KEY (created_by_id) REFERENCES public."user"(id);


--
-- Name: kb_category kb_category_organization_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.kb_category
    ADD CONSTRAINT kb_category_organization_id_fkey FOREIGN KEY (organization_id) REFERENCES public.organization(id) ON DELETE CASCADE;


--
-- Name: kb_category kb_category_teamspace_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.kb_category
    ADD CONSTRAINT kb_category_teamspace_id_fkey FOREIGN KEY (teamspace_id) REFERENCES public.teamspace(id) ON DELETE CASCADE;


--
-- Name: kb_category kb_category_updated_by_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.kb_category
    ADD CONSTRAINT kb_category_updated_by_id_fkey FOREIGN KEY (updated_by_id) REFERENCES public."user"(id);


--
-- Name: kb_feedback kb_feedback_article_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.kb_feedback
    ADD CONSTRAINT kb_feedback_article_id_fkey FOREIGN KEY (article_id) REFERENCES public.kb_article(id) ON DELETE CASCADE;


--
-- Name: kb_feedback kb_feedback_organization_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.kb_feedback
    ADD CONSTRAINT kb_feedback_organization_id_fkey FOREIGN KEY (organization_id) REFERENCES public.organization(id) ON DELETE CASCADE;


--
-- Name: kb_feedback kb_feedback_teamspace_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.kb_feedback
    ADD CONSTRAINT kb_feedback_teamspace_id_fkey FOREIGN KEY (teamspace_id) REFERENCES public.teamspace(id) ON DELETE CASCADE;


--
-- Name: kb_feedback kb_feedback_user_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.kb_feedback
    ADD CONSTRAINT kb_feedback_user_id_fkey FOREIGN KEY (user_id) REFERENCES public."user"(id);


--
-- Name: kb_subcategory kb_subcategory_category_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.kb_subcategory
    ADD CONSTRAINT kb_subcategory_category_id_fkey FOREIGN KEY (category_id) REFERENCES public.kb_category(id) ON DELETE CASCADE;


--
-- Name: kb_subcategory kb_subcategory_created_by_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.kb_subcategory
    ADD CONSTRAINT kb_subcategory_created_by_id_fkey FOREIGN KEY (created_by_id) REFERENCES public."user"(id);


--
-- Name: kb_subcategory kb_subcategory_organization_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.kb_subcategory
    ADD CONSTRAINT kb_subcategory_organization_id_fkey FOREIGN KEY (organization_id) REFERENCES public.organization(id) ON DELETE CASCADE;


--
-- Name: kb_subcategory kb_subcategory_teamspace_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.kb_subcategory
    ADD CONSTRAINT kb_subcategory_teamspace_id_fkey FOREIGN KEY (teamspace_id) REFERENCES public.teamspace(id) ON DELETE CASCADE;


--
-- Name: kb_subcategory kb_subcategory_updated_by_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.kb_subcategory
    ADD CONSTRAINT kb_subcategory_updated_by_id_fkey FOREIGN KEY (updated_by_id) REFERENCES public."user"(id);


--
-- Name: leave_request leave_request_created_by_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.leave_request
    ADD CONSTRAINT leave_request_created_by_id_fkey FOREIGN KEY (created_by_id) REFERENCES public."user"(id);


--
-- Name: leave_request leave_request_member_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.leave_request
    ADD CONSTRAINT leave_request_member_id_fkey FOREIGN KEY (member_id) REFERENCES public.teamspace_user(id) ON DELETE CASCADE;


--
-- Name: leave_request leave_request_organization_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.leave_request
    ADD CONSTRAINT leave_request_organization_id_fkey FOREIGN KEY (organization_id) REFERENCES public.organization(id) ON DELETE CASCADE;


--
-- Name: leave_request leave_request_reviewed_by_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.leave_request
    ADD CONSTRAINT leave_request_reviewed_by_id_fkey FOREIGN KEY (reviewed_by_id) REFERENCES public.teamspace_user(id) ON DELETE SET NULL;


--
-- Name: leave_request leave_request_teamspace_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.leave_request
    ADD CONSTRAINT leave_request_teamspace_id_fkey FOREIGN KEY (teamspace_id) REFERENCES public.teamspace(id) ON DELETE CASCADE;


--
-- Name: leave_request leave_request_updated_by_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.leave_request
    ADD CONSTRAINT leave_request_updated_by_id_fkey FOREIGN KEY (updated_by_id) REFERENCES public."user"(id);


--
-- Name: note note_member_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.note
    ADD CONSTRAINT note_member_id_fkey FOREIGN KEY (member_id) REFERENCES public.teamspace_user(id);


--
-- Name: note note_organization_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.note
    ADD CONSTRAINT note_organization_id_fkey FOREIGN KEY (organization_id) REFERENCES public.organization(id) ON DELETE CASCADE;


--
-- Name: note note_teamspace_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.note
    ADD CONSTRAINT note_teamspace_id_fkey FOREIGN KEY (teamspace_id) REFERENCES public.teamspace(id) ON DELETE CASCADE;


--
-- Name: oauth_connection oauth_connection_organization_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.oauth_connection
    ADD CONSTRAINT oauth_connection_organization_id_fkey FOREIGN KEY (organization_id) REFERENCES public.organization(id) ON DELETE CASCADE;


--
-- Name: oauth_connection oauth_connection_teamspace_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.oauth_connection
    ADD CONSTRAINT oauth_connection_teamspace_id_fkey FOREIGN KEY (teamspace_id) REFERENCES public.teamspace(id) ON DELETE CASCADE;


--
-- Name: oauth_connection oauth_connection_user_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.oauth_connection
    ADD CONSTRAINT oauth_connection_user_id_fkey FOREIGN KEY (user_id) REFERENCES public."user"(id);


--
-- Name: offboarding_assignment offboarding_assignment_completed_by_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.offboarding_assignment
    ADD CONSTRAINT offboarding_assignment_completed_by_id_fkey FOREIGN KEY (completed_by_id) REFERENCES public.teamspace_user(id);


--
-- Name: offboarding_assignment offboarding_assignment_member_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.offboarding_assignment
    ADD CONSTRAINT offboarding_assignment_member_id_fkey FOREIGN KEY (member_id) REFERENCES public.teamspace_user(id);


--
-- Name: offboarding_assignment offboarding_assignment_organization_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.offboarding_assignment
    ADD CONSTRAINT offboarding_assignment_organization_id_fkey FOREIGN KEY (organization_id) REFERENCES public.organization(id) ON DELETE CASCADE;


--
-- Name: offboarding_assignment offboarding_assignment_task_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.offboarding_assignment
    ADD CONSTRAINT offboarding_assignment_task_id_fkey FOREIGN KEY (task_id) REFERENCES public.offboarding_task(id);


--
-- Name: offboarding_assignment offboarding_assignment_teamspace_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.offboarding_assignment
    ADD CONSTRAINT offboarding_assignment_teamspace_id_fkey FOREIGN KEY (teamspace_id) REFERENCES public.teamspace(id) ON DELETE CASCADE;


--
-- Name: offboarding_task offboarding_task_organization_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.offboarding_task
    ADD CONSTRAINT offboarding_task_organization_id_fkey FOREIGN KEY (organization_id) REFERENCES public.organization(id) ON DELETE CASCADE;


--
-- Name: offboarding_task offboarding_task_teamspace_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.offboarding_task
    ADD CONSTRAINT offboarding_task_teamspace_id_fkey FOREIGN KEY (teamspace_id) REFERENCES public.teamspace(id) ON DELETE CASCADE;


--
-- Name: onboarding_record onboarding_record_contract_request_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.onboarding_record
    ADD CONSTRAINT onboarding_record_contract_request_id_fkey FOREIGN KEY (contract_request_id) REFERENCES public.signature_request(id);


--
-- Name: onboarding_record onboarding_record_created_by_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.onboarding_record
    ADD CONSTRAINT onboarding_record_created_by_id_fkey FOREIGN KEY (created_by_id) REFERENCES public."user"(id);


--
-- Name: onboarding_record onboarding_record_manager_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.onboarding_record
    ADD CONSTRAINT onboarding_record_manager_id_fkey FOREIGN KEY (manager_id) REFERENCES public.teamspace_user(id);


--
-- Name: onboarding_record onboarding_record_member_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.onboarding_record
    ADD CONSTRAINT onboarding_record_member_id_fkey FOREIGN KEY (member_id) REFERENCES public.teamspace_user(id);


--
-- Name: onboarding_record onboarding_record_offer_letter_request_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.onboarding_record
    ADD CONSTRAINT onboarding_record_offer_letter_request_id_fkey FOREIGN KEY (offer_letter_request_id) REFERENCES public.signature_request(id);


--
-- Name: onboarding_record onboarding_record_organization_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.onboarding_record
    ADD CONSTRAINT onboarding_record_organization_id_fkey FOREIGN KEY (organization_id) REFERENCES public.organization(id) ON DELETE CASCADE;


--
-- Name: onboarding_record onboarding_record_tax_form_attachment_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.onboarding_record
    ADD CONSTRAINT onboarding_record_tax_form_attachment_id_fkey FOREIGN KEY (tax_form_attachment_id) REFERENCES public.attachment(id);


--
-- Name: onboarding_record onboarding_record_teamspace_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.onboarding_record
    ADD CONSTRAINT onboarding_record_teamspace_id_fkey FOREIGN KEY (teamspace_id) REFERENCES public.teamspace(id) ON DELETE CASCADE;


--
-- Name: onboarding_record onboarding_record_updated_by_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.onboarding_record
    ADD CONSTRAINT onboarding_record_updated_by_id_fkey FOREIGN KEY (updated_by_id) REFERENCES public."user"(id);


--
-- Name: onboarding_task onboarding_task_onboarding_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.onboarding_task
    ADD CONSTRAINT onboarding_task_onboarding_id_fkey FOREIGN KEY (onboarding_id) REFERENCES public.onboarding_record(id);


--
-- Name: onboarding_task onboarding_task_organization_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.onboarding_task
    ADD CONSTRAINT onboarding_task_organization_id_fkey FOREIGN KEY (organization_id) REFERENCES public.organization(id) ON DELETE CASCADE;


--
-- Name: onboarding_task onboarding_task_teamspace_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.onboarding_task
    ADD CONSTRAINT onboarding_task_teamspace_id_fkey FOREIGN KEY (teamspace_id) REFERENCES public.teamspace(id) ON DELETE CASCADE;


--
-- Name: onboarding_task_template onboarding_task_template_organization_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.onboarding_task_template
    ADD CONSTRAINT onboarding_task_template_organization_id_fkey FOREIGN KEY (organization_id) REFERENCES public.organization(id) ON DELETE CASCADE;


--
-- Name: onboarding_task_template onboarding_task_template_teamspace_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.onboarding_task_template
    ADD CONSTRAINT onboarding_task_template_teamspace_id_fkey FOREIGN KEY (teamspace_id) REFERENCES public.teamspace(id) ON DELETE CASCADE;


--
-- Name: one_on_one_agenda_item one_on_one_agenda_item_added_by_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.one_on_one_agenda_item
    ADD CONSTRAINT one_on_one_agenda_item_added_by_id_fkey FOREIGN KEY (added_by_id) REFERENCES public.teamspace_user(id);


--
-- Name: one_on_one_agenda_item one_on_one_agenda_item_organization_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.one_on_one_agenda_item
    ADD CONSTRAINT one_on_one_agenda_item_organization_id_fkey FOREIGN KEY (organization_id) REFERENCES public.organization(id) ON DELETE CASCADE;


--
-- Name: one_on_one_agenda_item one_on_one_agenda_item_owner_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.one_on_one_agenda_item
    ADD CONSTRAINT one_on_one_agenda_item_owner_id_fkey FOREIGN KEY (owner_id) REFERENCES public.teamspace_user(id);


--
-- Name: one_on_one_agenda_item one_on_one_agenda_item_pair_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.one_on_one_agenda_item
    ADD CONSTRAINT one_on_one_agenda_item_pair_id_fkey FOREIGN KEY (pair_id) REFERENCES public.one_on_one_pair(id);


--
-- Name: one_on_one_agenda_item one_on_one_agenda_item_session_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.one_on_one_agenda_item
    ADD CONSTRAINT one_on_one_agenda_item_session_id_fkey FOREIGN KEY (session_id) REFERENCES public.one_on_one_session(id);


--
-- Name: one_on_one_agenda_item one_on_one_agenda_item_teamspace_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.one_on_one_agenda_item
    ADD CONSTRAINT one_on_one_agenda_item_teamspace_id_fkey FOREIGN KEY (teamspace_id) REFERENCES public.teamspace(id) ON DELETE CASCADE;


--
-- Name: one_on_one_pair one_on_one_pair_lead_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.one_on_one_pair
    ADD CONSTRAINT one_on_one_pair_lead_id_fkey FOREIGN KEY (lead_id) REFERENCES public.teamspace_user(id);


--
-- Name: one_on_one_pair one_on_one_pair_organization_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.one_on_one_pair
    ADD CONSTRAINT one_on_one_pair_organization_id_fkey FOREIGN KEY (organization_id) REFERENCES public.organization(id) ON DELETE CASCADE;


--
-- Name: one_on_one_pair one_on_one_pair_report_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.one_on_one_pair
    ADD CONSTRAINT one_on_one_pair_report_id_fkey FOREIGN KEY (report_id) REFERENCES public.teamspace_user(id);


--
-- Name: one_on_one_pair one_on_one_pair_teamspace_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.one_on_one_pair
    ADD CONSTRAINT one_on_one_pair_teamspace_id_fkey FOREIGN KEY (teamspace_id) REFERENCES public.teamspace(id) ON DELETE CASCADE;


--
-- Name: one_on_one_session one_on_one_session_organization_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.one_on_one_session
    ADD CONSTRAINT one_on_one_session_organization_id_fkey FOREIGN KEY (organization_id) REFERENCES public.organization(id) ON DELETE CASCADE;


--
-- Name: one_on_one_session one_on_one_session_pair_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.one_on_one_session
    ADD CONSTRAINT one_on_one_session_pair_id_fkey FOREIGN KEY (pair_id) REFERENCES public.one_on_one_pair(id);


--
-- Name: one_on_one_session one_on_one_session_teamspace_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.one_on_one_session
    ADD CONSTRAINT one_on_one_session_teamspace_id_fkey FOREIGN KEY (teamspace_id) REFERENCES public.teamspace(id) ON DELETE CASCADE;


--
-- Name: organization_invitation organization_invitation_invited_by_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.organization_invitation
    ADD CONSTRAINT organization_invitation_invited_by_id_fkey FOREIGN KEY (invited_by_id) REFERENCES public."user"(id) ON DELETE SET NULL;


--
-- Name: organization_invitation organization_invitation_organization_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.organization_invitation
    ADD CONSTRAINT organization_invitation_organization_id_fkey FOREIGN KEY (organization_id) REFERENCES public.organization(id) ON DELETE CASCADE;


--
-- Name: organization_user organization_user_invited_by_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.organization_user
    ADD CONSTRAINT organization_user_invited_by_id_fkey FOREIGN KEY (invited_by_id) REFERENCES public."user"(id) ON DELETE SET NULL;


--
-- Name: organization_user organization_user_organization_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.organization_user
    ADD CONSTRAINT organization_user_organization_id_fkey FOREIGN KEY (organization_id) REFERENCES public.organization(id) ON DELETE CASCADE;


--
-- Name: organization_user organization_user_user_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.organization_user
    ADD CONSTRAINT organization_user_user_id_fkey FOREIGN KEY (user_id) REFERENCES public."user"(id) ON DELETE CASCADE;


--
-- Name: person_note person_note_created_by_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.person_note
    ADD CONSTRAINT person_note_created_by_id_fkey FOREIGN KEY (created_by_id) REFERENCES public."user"(id);


--
-- Name: person_note person_note_deleted_by_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.person_note
    ADD CONSTRAINT person_note_deleted_by_id_fkey FOREIGN KEY (deleted_by_id) REFERENCES public."user"(id);


--
-- Name: person_note person_note_member_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.person_note
    ADD CONSTRAINT person_note_member_id_fkey FOREIGN KEY (member_id) REFERENCES public.teamspace_user(id);


--
-- Name: person_note person_note_organization_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.person_note
    ADD CONSTRAINT person_note_organization_id_fkey FOREIGN KEY (organization_id) REFERENCES public.organization(id) ON DELETE CASCADE;


--
-- Name: person_note person_note_teamspace_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.person_note
    ADD CONSTRAINT person_note_teamspace_id_fkey FOREIGN KEY (teamspace_id) REFERENCES public.teamspace(id) ON DELETE CASCADE;


--
-- Name: person_note person_note_updated_by_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.person_note
    ADD CONSTRAINT person_note_updated_by_id_fkey FOREIGN KEY (updated_by_id) REFERENCES public."user"(id);


--
-- Name: presence_settings presence_settings_organization_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.presence_settings
    ADD CONSTRAINT presence_settings_organization_id_fkey FOREIGN KEY (organization_id) REFERENCES public.organization(id) ON DELETE CASCADE;


--
-- Name: presence_settings presence_settings_teamspace_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.presence_settings
    ADD CONSTRAINT presence_settings_teamspace_id_fkey FOREIGN KEY (teamspace_id) REFERENCES public.teamspace(id) ON DELETE CASCADE;


--
-- Name: presence_signal presence_signal_member_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.presence_signal
    ADD CONSTRAINT presence_signal_member_id_fkey FOREIGN KEY (member_id) REFERENCES public.teamspace_user(id);


--
-- Name: presence_signal presence_signal_source_post_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.presence_signal
    ADD CONSTRAINT presence_signal_source_post_id_fkey FOREIGN KEY (source_post_id) REFERENCES public.update_post(id);


--
-- Name: presence_signal presence_signal_teamspace_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.presence_signal
    ADD CONSTRAINT presence_signal_teamspace_id_fkey FOREIGN KEY (teamspace_id) REFERENCES public.teamspace(id) ON DELETE CASCADE;


--
-- Name: presence_signal presence_signal_template_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.presence_signal
    ADD CONSTRAINT presence_signal_template_id_fkey FOREIGN KEY (template_id) REFERENCES public.update_template(id);


--
-- Name: project project_channel_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.project
    ADD CONSTRAINT project_channel_id_fkey FOREIGN KEY (channel_id) REFERENCES public.update_channel(id) ON DELETE SET NULL;


--
-- Name: project project_created_by_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.project
    ADD CONSTRAINT project_created_by_id_fkey FOREIGN KEY (created_by_id) REFERENCES public.teamspace_user(id) ON DELETE SET NULL;


--
-- Name: project project_organization_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.project
    ADD CONSTRAINT project_organization_id_fkey FOREIGN KEY (organization_id) REFERENCES public.organization(id) ON DELETE CASCADE;


--
-- Name: project project_owner_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.project
    ADD CONSTRAINT project_owner_id_fkey FOREIGN KEY (owner_id) REFERENCES public.teamspace_user(id) ON DELETE SET NULL;


--
-- Name: project project_teamspace_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.project
    ADD CONSTRAINT project_teamspace_id_fkey FOREIGN KEY (teamspace_id) REFERENCES public.teamspace(id) ON DELETE CASCADE;


--
-- Name: punch_change_request punch_change_request_clock_punch_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.punch_change_request
    ADD CONSTRAINT punch_change_request_clock_punch_id_fkey FOREIGN KEY (clock_punch_id) REFERENCES public.clock_punch(id) ON DELETE CASCADE;


--
-- Name: punch_change_request punch_change_request_created_by_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.punch_change_request
    ADD CONSTRAINT punch_change_request_created_by_id_fkey FOREIGN KEY (created_by_id) REFERENCES public."user"(id);


--
-- Name: punch_change_request punch_change_request_member_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.punch_change_request
    ADD CONSTRAINT punch_change_request_member_id_fkey FOREIGN KEY (member_id) REFERENCES public.teamspace_user(id) ON DELETE CASCADE;


--
-- Name: punch_change_request punch_change_request_organization_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.punch_change_request
    ADD CONSTRAINT punch_change_request_organization_id_fkey FOREIGN KEY (organization_id) REFERENCES public.organization(id) ON DELETE CASCADE;


--
-- Name: punch_change_request punch_change_request_reviewed_by_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.punch_change_request
    ADD CONSTRAINT punch_change_request_reviewed_by_id_fkey FOREIGN KEY (reviewed_by_id) REFERENCES public.teamspace_user(id) ON DELETE SET NULL;


--
-- Name: punch_change_request punch_change_request_teamspace_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.punch_change_request
    ADD CONSTRAINT punch_change_request_teamspace_id_fkey FOREIGN KEY (teamspace_id) REFERENCES public.teamspace(id) ON DELETE CASCADE;


--
-- Name: punch_change_request punch_change_request_updated_by_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.punch_change_request
    ADD CONSTRAINT punch_change_request_updated_by_id_fkey FOREIGN KEY (updated_by_id) REFERENCES public."user"(id);


--
-- Name: push_subscription push_subscription_organization_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.push_subscription
    ADD CONSTRAINT push_subscription_organization_id_fkey FOREIGN KEY (organization_id) REFERENCES public.organization(id) ON DELETE CASCADE;


--
-- Name: push_subscription push_subscription_teamspace_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.push_subscription
    ADD CONSTRAINT push_subscription_teamspace_id_fkey FOREIGN KEY (teamspace_id) REFERENCES public.teamspace(id) ON DELETE CASCADE;


--
-- Name: push_subscription push_subscription_user_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.push_subscription
    ADD CONSTRAINT push_subscription_user_id_fkey FOREIGN KEY (user_id) REFERENCES public."user"(id);


--
-- Name: refresh_token refresh_token_user_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.refresh_token
    ADD CONSTRAINT refresh_token_user_id_fkey FOREIGN KEY (user_id) REFERENCES public."user"(id);


--
-- Name: resources_settings resources_settings_organization_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.resources_settings
    ADD CONSTRAINT resources_settings_organization_id_fkey FOREIGN KEY (organization_id) REFERENCES public.organization(id) ON DELETE CASCADE;


--
-- Name: resources_settings resources_settings_teamspace_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.resources_settings
    ADD CONSTRAINT resources_settings_teamspace_id_fkey FOREIGN KEY (teamspace_id) REFERENCES public.teamspace(id) ON DELETE CASCADE;


--
-- Name: service_location service_location_contact_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.service_location
    ADD CONSTRAINT service_location_contact_id_fkey FOREIGN KEY (contact_id) REFERENCES public.contact(id) ON DELETE CASCADE;


--
-- Name: service_location service_location_organization_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.service_location
    ADD CONSTRAINT service_location_organization_id_fkey FOREIGN KEY (organization_id) REFERENCES public.organization(id) ON DELETE CASCADE;


--
-- Name: service_location service_location_teamspace_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.service_location
    ADD CONSTRAINT service_location_teamspace_id_fkey FOREIGN KEY (teamspace_id) REFERENCES public.teamspace(id) ON DELETE CASCADE;


--
-- Name: signature_audit_log signature_audit_log_actor_user_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.signature_audit_log
    ADD CONSTRAINT signature_audit_log_actor_user_id_fkey FOREIGN KEY (actor_user_id) REFERENCES public.teamspace_user(id);


--
-- Name: signature_audit_log signature_audit_log_organization_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.signature_audit_log
    ADD CONSTRAINT signature_audit_log_organization_id_fkey FOREIGN KEY (organization_id) REFERENCES public.organization(id) ON DELETE CASCADE;


--
-- Name: signature_audit_log signature_audit_log_recipient_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.signature_audit_log
    ADD CONSTRAINT signature_audit_log_recipient_id_fkey FOREIGN KEY (recipient_id) REFERENCES public.signature_recipient(id);


--
-- Name: signature_audit_log signature_audit_log_request_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.signature_audit_log
    ADD CONSTRAINT signature_audit_log_request_id_fkey FOREIGN KEY (request_id) REFERENCES public.signature_request(id);


--
-- Name: signature_audit_log signature_audit_log_teamspace_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.signature_audit_log
    ADD CONSTRAINT signature_audit_log_teamspace_id_fkey FOREIGN KEY (teamspace_id) REFERENCES public.teamspace(id) ON DELETE CASCADE;


--
-- Name: signature_recipient signature_recipient_organization_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.signature_recipient
    ADD CONSTRAINT signature_recipient_organization_id_fkey FOREIGN KEY (organization_id) REFERENCES public.organization(id) ON DELETE CASCADE;


--
-- Name: signature_recipient signature_recipient_request_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.signature_recipient
    ADD CONSTRAINT signature_recipient_request_id_fkey FOREIGN KEY (request_id) REFERENCES public.signature_request(id);


--
-- Name: signature_recipient signature_recipient_teamspace_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.signature_recipient
    ADD CONSTRAINT signature_recipient_teamspace_id_fkey FOREIGN KEY (teamspace_id) REFERENCES public.teamspace(id) ON DELETE CASCADE;


--
-- Name: signature_recipient signature_recipient_user_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.signature_recipient
    ADD CONSTRAINT signature_recipient_user_id_fkey FOREIGN KEY (user_id) REFERENCES public."user"(id);


--
-- Name: signature_request signature_request_created_by_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.signature_request
    ADD CONSTRAINT signature_request_created_by_id_fkey FOREIGN KEY (created_by_id) REFERENCES public.teamspace_user(id);


--
-- Name: signature_request signature_request_organization_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.signature_request
    ADD CONSTRAINT signature_request_organization_id_fkey FOREIGN KEY (organization_id) REFERENCES public.organization(id) ON DELETE CASCADE;


--
-- Name: signature_request signature_request_original_attachment_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.signature_request
    ADD CONSTRAINT signature_request_original_attachment_id_fkey FOREIGN KEY (original_attachment_id) REFERENCES public.attachment(id);


--
-- Name: signature_request signature_request_signed_attachment_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.signature_request
    ADD CONSTRAINT signature_request_signed_attachment_id_fkey FOREIGN KEY (signed_attachment_id) REFERENCES public.attachment(id);


--
-- Name: signature_request signature_request_teamspace_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.signature_request
    ADD CONSTRAINT signature_request_teamspace_id_fkey FOREIGN KEY (teamspace_id) REFERENCES public.teamspace(id) ON DELETE CASCADE;


--
-- Name: update_area sync_area_teamspace_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.update_area
    ADD CONSTRAINT sync_area_teamspace_id_fkey FOREIGN KEY (teamspace_id) REFERENCES public.teamspace(id) ON DELETE CASCADE;


--
-- Name: update_post_ack sync_post_ack_member_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.update_post_ack
    ADD CONSTRAINT sync_post_ack_member_id_fkey FOREIGN KEY (member_id) REFERENCES public.teamspace_user(id);


--
-- Name: update_post_ack sync_post_ack_post_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.update_post_ack
    ADD CONSTRAINT sync_post_ack_post_id_fkey FOREIGN KEY (post_id) REFERENCES public.update_post(id) ON DELETE CASCADE;


--
-- Name: update_post_ack sync_post_ack_teamspace_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.update_post_ack
    ADD CONSTRAINT sync_post_ack_teamspace_id_fkey FOREIGN KEY (teamspace_id) REFERENCES public.teamspace(id) ON DELETE CASCADE;


--
-- Name: update_post sync_post_area_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.update_post
    ADD CONSTRAINT sync_post_area_id_fkey FOREIGN KEY (area_id) REFERENCES public.update_area(id) ON DELETE SET NULL;


--
-- Name: update_week_review sync_week_review_post_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.update_week_review
    ADD CONSTRAINT sync_week_review_post_id_fkey FOREIGN KEY (post_id) REFERENCES public.update_post(id) ON DELETE SET NULL;


--
-- Name: update_week_review sync_week_review_sent_by_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.update_week_review
    ADD CONSTRAINT sync_week_review_sent_by_id_fkey FOREIGN KEY (sent_by_id) REFERENCES public.teamspace_user(id);


--
-- Name: update_week_review sync_week_review_teamspace_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.update_week_review
    ADD CONSTRAINT sync_week_review_teamspace_id_fkey FOREIGN KEY (teamspace_id) REFERENCES public.teamspace(id) ON DELETE CASCADE;


--
-- Name: system_notification system_notification_organization_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.system_notification
    ADD CONSTRAINT system_notification_organization_id_fkey FOREIGN KEY (organization_id) REFERENCES public.organization(id) ON DELETE CASCADE;


--
-- Name: system_notification system_notification_teamspace_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.system_notification
    ADD CONSTRAINT system_notification_teamspace_id_fkey FOREIGN KEY (teamspace_id) REFERENCES public.teamspace(id) ON DELETE CASCADE;


--
-- Name: system_notification system_notification_user_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.system_notification
    ADD CONSTRAINT system_notification_user_id_fkey FOREIGN KEY (user_id) REFERENCES public."user"(id);


--
-- Name: tax_form_record tax_form_record_attachment_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.tax_form_record
    ADD CONSTRAINT tax_form_record_attachment_id_fkey FOREIGN KEY (attachment_id) REFERENCES public.attachment(id);


--
-- Name: tax_form_record tax_form_record_created_by_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.tax_form_record
    ADD CONSTRAINT tax_form_record_created_by_id_fkey FOREIGN KEY (created_by_id) REFERENCES public.teamspace_user(id);


--
-- Name: tax_form_record tax_form_record_member_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.tax_form_record
    ADD CONSTRAINT tax_form_record_member_id_fkey FOREIGN KEY (member_id) REFERENCES public.teamspace_user(id);


--
-- Name: tax_form_record tax_form_record_organization_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.tax_form_record
    ADD CONSTRAINT tax_form_record_organization_id_fkey FOREIGN KEY (organization_id) REFERENCES public.organization(id) ON DELETE CASCADE;


--
-- Name: tax_form_record tax_form_record_teamspace_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.tax_form_record
    ADD CONSTRAINT tax_form_record_teamspace_id_fkey FOREIGN KEY (teamspace_id) REFERENCES public.teamspace(id) ON DELETE CASCADE;


--
-- Name: teamspace teamspace_business_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.teamspace
    ADD CONSTRAINT teamspace_business_id_fkey FOREIGN KEY (organization_id) REFERENCES public.organization(id);


--
-- Name: teamspace teamspace_deleted_by_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.teamspace
    ADD CONSTRAINT teamspace_deleted_by_id_fkey FOREIGN KEY (deleted_by_id) REFERENCES public."user"(id);


--
-- Name: teamspace_invite teamspace_invite_created_by_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.teamspace_invite
    ADD CONSTRAINT teamspace_invite_created_by_id_fkey FOREIGN KEY (created_by_id) REFERENCES public."user"(id);


--
-- Name: teamspace_invite teamspace_invite_invited_by_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.teamspace_invite
    ADD CONSTRAINT teamspace_invite_invited_by_id_fkey FOREIGN KEY (invited_by_id) REFERENCES public.teamspace_user(id) ON DELETE SET NULL;


--
-- Name: teamspace_invite teamspace_invite_organization_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.teamspace_invite
    ADD CONSTRAINT teamspace_invite_organization_id_fkey FOREIGN KEY (organization_id) REFERENCES public.organization(id) ON DELETE CASCADE;


--
-- Name: teamspace_invite teamspace_invite_teamspace_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.teamspace_invite
    ADD CONSTRAINT teamspace_invite_teamspace_id_fkey FOREIGN KEY (teamspace_id) REFERENCES public.teamspace(id) ON DELETE CASCADE;


--
-- Name: teamspace_invite teamspace_invite_updated_by_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.teamspace_invite
    ADD CONSTRAINT teamspace_invite_updated_by_id_fkey FOREIGN KEY (updated_by_id) REFERENCES public."user"(id);


--
-- Name: teamspace_settings teamspace_settings_organization_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.teamspace_settings
    ADD CONSTRAINT teamspace_settings_organization_id_fkey FOREIGN KEY (organization_id) REFERENCES public.organization(id) ON DELETE CASCADE;


--
-- Name: teamspace_settings teamspace_settings_teamspace_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.teamspace_settings
    ADD CONSTRAINT teamspace_settings_teamspace_id_fkey FOREIGN KEY (teamspace_id) REFERENCES public.teamspace(id) ON DELETE CASCADE;


--
-- Name: teamspace_user teamspace_user_deleted_by_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.teamspace_user
    ADD CONSTRAINT teamspace_user_deleted_by_id_fkey FOREIGN KEY (deleted_by_id) REFERENCES public."user"(id);


--
-- Name: teamspace_user teamspace_user_manager_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.teamspace_user
    ADD CONSTRAINT teamspace_user_manager_id_fkey FOREIGN KEY (manager_id) REFERENCES public.teamspace_user(id);


--
-- Name: teamspace_user teamspace_user_organization_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.teamspace_user
    ADD CONSTRAINT teamspace_user_organization_id_fkey FOREIGN KEY (organization_id) REFERENCES public.organization(id) ON DELETE CASCADE;


--
-- Name: teamspace_user teamspace_user_organization_user_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.teamspace_user
    ADD CONSTRAINT teamspace_user_organization_user_id_fkey FOREIGN KEY (organization_user_id) REFERENCES public.organization_user(id) ON DELETE CASCADE;


--
-- Name: teamspace_user teamspace_user_teamspace_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.teamspace_user
    ADD CONSTRAINT teamspace_user_teamspace_id_fkey FOREIGN KEY (teamspace_id) REFERENCES public.teamspace(id) ON DELETE CASCADE;


--
-- Name: teamspace_user teamspace_user_user_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.teamspace_user
    ADD CONSTRAINT teamspace_user_user_id_fkey FOREIGN KEY (user_id) REFERENCES public."user"(id) ON DELETE CASCADE;


--
-- Name: time_entry time_entry_approved_by_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.time_entry
    ADD CONSTRAINT time_entry_approved_by_id_fkey FOREIGN KEY (approved_by_id) REFERENCES public.teamspace_user(id) ON DELETE SET NULL;


--
-- Name: time_entry time_entry_created_by_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.time_entry
    ADD CONSTRAINT time_entry_created_by_id_fkey FOREIGN KEY (created_by_id) REFERENCES public."user"(id);


--
-- Name: time_entry time_entry_member_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.time_entry
    ADD CONSTRAINT time_entry_member_id_fkey FOREIGN KEY (member_id) REFERENCES public.teamspace_user(id) ON DELETE CASCADE;


--
-- Name: time_entry time_entry_organization_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.time_entry
    ADD CONSTRAINT time_entry_organization_id_fkey FOREIGN KEY (organization_id) REFERENCES public.organization(id) ON DELETE CASCADE;


--
-- Name: time_entry time_entry_teamspace_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.time_entry
    ADD CONSTRAINT time_entry_teamspace_id_fkey FOREIGN KEY (teamspace_id) REFERENCES public.teamspace(id) ON DELETE CASCADE;


--
-- Name: time_entry time_entry_updated_by_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.time_entry
    ADD CONSTRAINT time_entry_updated_by_id_fkey FOREIGN KEY (updated_by_id) REFERENCES public."user"(id);


--
-- Name: timesheet_notification_recipients timesheet_notification_recipients_settings_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.timesheet_notification_recipients
    ADD CONSTRAINT timesheet_notification_recipients_settings_id_fkey FOREIGN KEY (settings_id) REFERENCES public.presence_settings(id) ON DELETE CASCADE;


--
-- Name: timesheet_notification_recipients timesheet_notification_recipients_user_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.timesheet_notification_recipients
    ADD CONSTRAINT timesheet_notification_recipients_user_id_fkey FOREIGN KEY (user_id) REFERENCES public."user"(id) ON DELETE CASCADE;


--
-- Name: update_area update_area_organization_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.update_area
    ADD CONSTRAINT update_area_organization_id_fkey FOREIGN KEY (organization_id) REFERENCES public.organization(id) ON DELETE CASCADE;


--
-- Name: update_channel update_channel_organization_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.update_channel
    ADD CONSTRAINT update_channel_organization_id_fkey FOREIGN KEY (organization_id) REFERENCES public.organization(id) ON DELETE CASCADE;


--
-- Name: update_channel_read_state update_channel_read_state_channel_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.update_channel_read_state
    ADD CONSTRAINT update_channel_read_state_channel_id_fkey FOREIGN KEY (channel_id) REFERENCES public.update_channel(id) ON DELETE CASCADE;


--
-- Name: update_channel_read_state update_channel_read_state_member_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.update_channel_read_state
    ADD CONSTRAINT update_channel_read_state_member_id_fkey FOREIGN KEY (member_id) REFERENCES public.teamspace_user(id) ON DELETE CASCADE;


--
-- Name: update_channel_read_state update_channel_read_state_organization_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.update_channel_read_state
    ADD CONSTRAINT update_channel_read_state_organization_id_fkey FOREIGN KEY (organization_id) REFERENCES public.organization(id) ON DELETE CASCADE;


--
-- Name: update_channel_read_state update_channel_read_state_teamspace_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.update_channel_read_state
    ADD CONSTRAINT update_channel_read_state_teamspace_id_fkey FOREIGN KEY (teamspace_id) REFERENCES public.teamspace(id) ON DELETE CASCADE;


--
-- Name: update_follow update_follow_organization_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.update_follow
    ADD CONSTRAINT update_follow_organization_id_fkey FOREIGN KEY (organization_id) REFERENCES public.organization(id) ON DELETE CASCADE;


--
-- Name: update_nudge_log update_nudge_log_organization_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.update_nudge_log
    ADD CONSTRAINT update_nudge_log_organization_id_fkey FOREIGN KEY (organization_id) REFERENCES public.organization(id) ON DELETE CASCADE;


--
-- Name: update_post_ack update_post_ack_organization_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.update_post_ack
    ADD CONSTRAINT update_post_ack_organization_id_fkey FOREIGN KEY (organization_id) REFERENCES public.organization(id) ON DELETE CASCADE;


--
-- Name: update_post update_post_last_reply_member_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.update_post
    ADD CONSTRAINT update_post_last_reply_member_id_fkey FOREIGN KEY (last_reply_member_id) REFERENCES public.teamspace_user(id);


--
-- Name: update_post update_post_organization_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.update_post
    ADD CONSTRAINT update_post_organization_id_fkey FOREIGN KEY (organization_id) REFERENCES public.organization(id) ON DELETE CASCADE;


--
-- Name: update_post_reaction update_post_reaction_organization_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.update_post_reaction
    ADD CONSTRAINT update_post_reaction_organization_id_fkey FOREIGN KEY (organization_id) REFERENCES public.organization(id) ON DELETE CASCADE;


--
-- Name: update_post update_post_target_user_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.update_post
    ADD CONSTRAINT update_post_target_user_id_fkey FOREIGN KEY (target_user_id) REFERENCES public."user"(id);


--
-- Name: update_webhook update_webhook_organization_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.update_webhook
    ADD CONSTRAINT update_webhook_organization_id_fkey FOREIGN KEY (organization_id) REFERENCES public.organization(id) ON DELETE CASCADE;


--
-- Name: update_week_review update_week_review_organization_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.update_week_review
    ADD CONSTRAINT update_week_review_organization_id_fkey FOREIGN KEY (organization_id) REFERENCES public.organization(id) ON DELETE CASCADE;


--
-- Name: user_setting user_setting_organization_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.user_setting
    ADD CONSTRAINT user_setting_organization_id_fkey FOREIGN KEY (organization_id) REFERENCES public.organization(id) ON DELETE CASCADE;


--
-- Name: user_setting user_setting_teamspace_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.user_setting
    ADD CONSTRAINT user_setting_teamspace_id_fkey FOREIGN KEY (teamspace_id) REFERENCES public.teamspace(id) ON DELETE CASCADE;


--
-- Name: user_setting user_setting_user_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.user_setting
    ADD CONSTRAINT user_setting_user_id_fkey FOREIGN KEY (user_id) REFERENCES public."user"(id);


--
-- Name: update_webhook webhook_channel_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.update_webhook
    ADD CONSTRAINT webhook_channel_id_fkey FOREIGN KEY (channel_id) REFERENCES public.update_channel(id) ON DELETE CASCADE;


--
-- Name: update_webhook webhook_created_by_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.update_webhook
    ADD CONSTRAINT webhook_created_by_id_fkey FOREIGN KEY (created_by_id) REFERENCES public.teamspace_user(id);


--
-- Name: update_webhook webhook_dm_thread_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.update_webhook
    ADD CONSTRAINT webhook_dm_thread_id_fkey FOREIGN KEY (dm_thread_id) REFERENCES public.dm_thread(id) ON DELETE CASCADE;


--
-- Name: update_webhook webhook_teamspace_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.update_webhook
    ADD CONSTRAINT webhook_teamspace_id_fkey FOREIGN KEY (teamspace_id) REFERENCES public.teamspace(id) ON DELETE CASCADE;


--
-- Name: weekly_plan weekly_plan_created_by_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.weekly_plan
    ADD CONSTRAINT weekly_plan_created_by_id_fkey FOREIGN KEY (created_by_id) REFERENCES public.teamspace_user(id);


--
-- Name: weekly_plan_goal weekly_plan_goal_plan_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.weekly_plan_goal
    ADD CONSTRAINT weekly_plan_goal_plan_id_fkey FOREIGN KEY (plan_id) REFERENCES public.weekly_plan(id) ON DELETE CASCADE;


--
-- Name: weekly_plan weekly_plan_organization_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.weekly_plan
    ADD CONSTRAINT weekly_plan_organization_id_fkey FOREIGN KEY (organization_id) REFERENCES public.organization(id) ON DELETE CASCADE;


--
-- Name: weekly_plan weekly_plan_teamspace_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.weekly_plan
    ADD CONSTRAINT weekly_plan_teamspace_id_fkey FOREIGN KEY (teamspace_id) REFERENCES public.teamspace(id) ON DELETE CASCADE;


--
-- Name: working_agreement_ack working_agreement_ack_agreement_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.working_agreement_ack
    ADD CONSTRAINT working_agreement_ack_agreement_id_fkey FOREIGN KEY (agreement_id) REFERENCES public.working_agreement(id);


--
-- Name: working_agreement_ack working_agreement_ack_member_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.working_agreement_ack
    ADD CONSTRAINT working_agreement_ack_member_id_fkey FOREIGN KEY (member_id) REFERENCES public.teamspace_user(id);


--
-- Name: working_agreement_ack working_agreement_ack_organization_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.working_agreement_ack
    ADD CONSTRAINT working_agreement_ack_organization_id_fkey FOREIGN KEY (organization_id) REFERENCES public.organization(id) ON DELETE CASCADE;


--
-- Name: working_agreement_ack working_agreement_ack_teamspace_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.working_agreement_ack
    ADD CONSTRAINT working_agreement_ack_teamspace_id_fkey FOREIGN KEY (teamspace_id) REFERENCES public.teamspace(id) ON DELETE CASCADE;


--
-- Name: working_agreement working_agreement_organization_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.working_agreement
    ADD CONSTRAINT working_agreement_organization_id_fkey FOREIGN KEY (organization_id) REFERENCES public.organization(id) ON DELETE CASCADE;


--
-- Name: working_agreement working_agreement_teamspace_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.working_agreement
    ADD CONSTRAINT working_agreement_teamspace_id_fkey FOREIGN KEY (teamspace_id) REFERENCES public.teamspace(id) ON DELETE CASCADE;


--
-- Name: working_agreement working_agreement_updated_by_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.working_agreement
    ADD CONSTRAINT working_agreement_updated_by_id_fkey FOREIGN KEY (updated_by_id) REFERENCES public.teamspace_user(id);


--
-- PostgreSQL database dump complete
--

\unrestrict cNtJfufvi0V9IpOEadAonmpgqfCf0TkgnrTlwaTB5aef7Eoh2qVoOhIL3WSExp3

