# Password Groups Design

## Goal

Add password groups as an album-like organization layer for entries, while keeping tags as lightweight descriptive labels.

## Scope

- Entry edit forms can add existing tags by clicking chips, while still allowing manual tag input.
- Each entry can belong to multiple password groups.
- A password group has a name and description.
- The sidebar gets a single `密码组模式` view entry instead of listing every group.
- Password group mode shows group cards in the main workspace.
- Clicking a group card switches back to the entry list filtered by that group.
- Existing entries without `groups` remain valid and behave as ungrouped entries.

## Data Model

Entries gain:

```json
"groups": ["工作账号", "服务器"]
```

Vault metadata gains:

```json
"groups_meta": {
  "工作账号": {
    "description": "公司系统、云平台、协作工具"
  }
}
```

Group counts and latest update time are derived from entries at request time.

## UI Behavior

- Sidebar view section contains `全部条目`, `星标条目`, and `密码组模式`.
- Password group mode replaces the entry grid with group cards.
- A group card shows name, description, entry count, and latest update time.
- Clicking a card applies the group filter and shows normal entry cards.
- The active list state shows `密码组：<name>` and can be cleared with existing clear-list behavior.
- Entry forms include tag chips for existing tags and group chips for existing groups.
- Entry forms allow creating group names inline by typing and pressing Enter.

## API

- `GET /groups`: list groups with `name`, `description`, `count`, and `updated_at`.
- `POST /groups`: create a group metadata record.
- `PUT /groups/{group_name}`: rename a group and/or update its description.
- `DELETE /groups/{group_name}`: remove the group from metadata and from all entries; entries are not deleted.
- `GET /entries?group=<name>` filters entries by group.

## Compatibility

`groups` defaults to an empty list. `groups_meta` defaults to an empty dict. Import/export uses the normal vault model serialization and remains backward compatible.
