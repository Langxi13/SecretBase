use std::collections::HashSet;

use super::super::types::AssistantAction;
use crate::mobile::error::MobileError;

pub(in crate::mobile::ai) fn ordered_selected_actions<'a>(
    actions: &'a [AssistantAction],
    selected: &HashSet<String>,
) -> Result<Vec<&'a AssistantAction>, MobileError> {
    let selected_actions = actions
        .iter()
        .enumerate()
        .filter(|(_, action)| selected.contains(&action.id))
        .collect::<Vec<_>>();
    validate_conflicts(&selected_actions)?;

    let mut ordered = selected_actions;
    ordered.sort_by_key(|(index, action)| (execution_priority(&action.action_type), *index));
    Ok(ordered.into_iter().map(|(_, action)| action).collect())
}

fn validate_conflicts(actions: &[(usize, &AssistantAction)]) -> Result<(), MobileError> {
    for (index, (_, left)) in actions.iter().enumerate() {
        for (_, right) in actions.iter().skip(index + 1) {
            if actions_conflict(left, right) {
                return Err(MobileError::new(
                    "AI_PLAN_CONFLICT",
                    "所选 AI 计划存在顺序冲突，请取消其中一项后重试",
                ));
            }
        }
    }
    Ok(())
}

fn actions_conflict(left: &AssistantAction, right: &AssistantAction) -> bool {
    duplicate_target(left, right)
        || group_conflict(left, right)
        || group_conflict(right, left)
        || tag_conflict(left, right)
        || tag_conflict(right, left)
        || field_conflict(left, right)
}

fn duplicate_target(left: &AssistantAction, right: &AssistantAction) -> bool {
    match (left.action_type.as_str(), right.action_type.as_str()) {
        ("create_group", "create_group") | ("create_tag", "create_tag") => {
            same_optional(&left.name, &right.name)
        }
        ("rename_entry", "rename_entry") => same_optional(&left.entry_id, &right.entry_id),
        ("add_empty_field", "add_empty_field") => {
            same_optional(&left.entry_id, &right.entry_id) && same_optional(&left.name, &right.name)
        }
        _ => false,
    }
}

fn group_conflict(update: &AssistantAction, other: &AssistantAction) -> bool {
    if update.action_type != "update_group" {
        return false;
    }
    if other.action_type == "update_group" {
        return names_overlap(
            [update.name.as_deref(), update.new_name.as_deref()],
            [other.name.as_deref(), other.new_name.as_deref()],
        );
    }
    let Some(destination) = update.new_name.as_deref() else {
        return false;
    };
    (other.action_type == "create_group" && other.name.as_deref() == Some(destination))
        || (other.action_type == "assign_groups"
            && contains_name(&other.add, &other.remove, destination))
}

fn tag_conflict(governance: &AssistantAction, other: &AssistantAction) -> bool {
    let governed = governed_tags(governance);
    if governed.is_empty() {
        return false;
    }
    if matches!(
        other.action_type.as_str(),
        "update_tag" | "delete_tag" | "merge_tags"
    ) {
        return governed
            .iter()
            .any(|name| governed_tags(other).contains(name));
    }
    if other.action_type == "create_tag" {
        return governance.action_type == "update_tag"
            && governance.new_name.is_some()
            && governance.new_name == other.name;
    }
    if other.action_type == "assign_tags" {
        let affected = match governance.action_type.as_str() {
            "update_tag" => governance.new_name.as_deref(),
            "delete_tag" => governance.name.as_deref(),
            _ => None,
        };
        return affected.is_some_and(|name| contains_name(&other.add, &other.remove, name));
    }
    false
}

fn field_conflict(left: &AssistantAction, right: &AssistantAction) -> bool {
    if same_field(left, right) {
        if left.action_type == right.action_type {
            return true;
        }
        if left.action_type == "create_entry_from_field"
            || right.action_type == "create_entry_from_field"
        {
            return true;
        }
    }

    if left.action_type == "rename_field" && right.action_type == "add_empty_field" {
        return same_optional(&left.entry_id, &right.entry_id)
            && same_optional(&left.new_name, &right.name);
    }
    if right.action_type == "rename_field" && left.action_type == "add_empty_field" {
        return same_optional(&right.entry_id, &left.entry_id)
            && same_optional(&right.new_name, &left.name);
    }
    if left.action_type == "rename_field" && right.action_type == "rename_field" {
        return same_optional(&left.entry_id, &right.entry_id)
            && names_overlap(
                [left.field_name.as_deref(), left.new_name.as_deref()],
                [right.field_name.as_deref(), right.new_name.as_deref()],
            );
    }
    false
}

fn governed_tags(action: &AssistantAction) -> HashSet<String> {
    match action.action_type.as_str() {
        "update_tag" => [action.name.clone(), action.new_name.clone()]
            .into_iter()
            .flatten()
            .collect(),
        "delete_tag" => action.name.clone().into_iter().collect(),
        "merge_tags" => action
            .source_tags
            .iter()
            .cloned()
            .chain(action.target_tag.clone())
            .collect(),
        _ => HashSet::new(),
    }
}

fn same_field(left: &AssistantAction, right: &AssistantAction) -> bool {
    left.entry_id.is_some()
        && left.entry_id == right.entry_id
        && left.field_index.is_some()
        && left.field_index == right.field_index
        && left.field_name.is_some()
        && left.field_name == right.field_name
}

fn same_optional(left: &Option<String>, right: &Option<String>) -> bool {
    left.is_some() && left == right
}

fn names_overlap<const L: usize, const R: usize>(
    left: [Option<&str>; L],
    right: [Option<&str>; R],
) -> bool {
    left.into_iter()
        .flatten()
        .any(|name| right.iter().flatten().any(|other| name == *other))
}

fn contains_name(add: &[String], remove: &[String], name: &str) -> bool {
    add.iter().chain(remove).any(|item| item == name)
}

fn execution_priority(action_type: &str) -> u8 {
    match action_type {
        "create_group" | "create_tag" => 10,
        "assign_groups" | "assign_tags" => 20,
        "create_entry_template" | "create_entry_from_field" => 30,
        "set_field_flags" => 40,
        "add_empty_field" => 45,
        "rename_field" | "rename_entry" => 50,
        "update_group" | "update_tag" => 60,
        "merge_tags" => 70,
        "delete_tag" => 80,
        _ => 100,
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::mobile::ai::types::ParsedField;

    fn action(id: &str, action_type: &str) -> AssistantAction {
        AssistantAction {
            id: id.to_string(),
            action_type: action_type.to_string(),
            entry_ids: Vec::new(),
            entry_id: None,
            source_entry_id: None,
            field_index: None,
            field_name: None,
            name: None,
            new_name: None,
            title: None,
            description: String::new(),
            color: None,
            source_tags: Vec::new(),
            target_tag: None,
            add: Vec::new(),
            remove: Vec::new(),
            tags: Vec::new(),
            groups: Vec::new(),
            fields: Vec::<ParsedField>::new(),
            copyable: None,
            hidden: None,
            reason: String::new(),
        }
    }

    #[test]
    fn mixed_domains_are_sorted_for_atomic_application() {
        let mut rename = action("rename", "rename_entry");
        rename.entry_id = Some("entry-1".to_string());
        rename.new_name = Some("新标题".to_string());
        let mut create_tag = action("tag", "create_tag");
        create_tag.name = Some("工作".to_string());
        let actions = vec![rename, create_tag];
        let selected = HashSet::from(["rename".to_string(), "tag".to_string()]);

        let ordered = ordered_selected_actions(&actions, &selected).unwrap();
        assert_eq!(ordered[0].action_type, "create_tag");
        assert_eq!(ordered[1].action_type, "rename_entry");
    }

    #[test]
    fn conflicting_tag_delete_and_assignment_are_blocked() {
        let mut delete = action("delete", "delete_tag");
        delete.name = Some("旧标签".to_string());
        let mut assign = action("assign", "assign_tags");
        assign.add = vec!["旧标签".to_string()];
        let actions = vec![delete, assign];
        let selected = HashSet::from(["delete".to_string(), "assign".to_string()]);

        let error = ordered_selected_actions(&actions, &selected).unwrap_err();
        assert!(matches!(
            error,
            MobileError::Failure { ref code, .. } if code == "AI_PLAN_CONFLICT"
        ));
    }
}
