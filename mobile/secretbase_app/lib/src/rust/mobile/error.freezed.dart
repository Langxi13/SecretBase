// GENERATED CODE - DO NOT MODIFY BY HAND
// coverage:ignore-file
// ignore_for_file: type=lint
// ignore_for_file: unused_element, deprecated_member_use, deprecated_member_use_from_same_package, use_function_type_syntax_for_parameters, unnecessary_const, avoid_init_to_null, invalid_override_different_default_values_named, prefer_expression_function_bodies, annotate_overrides, invalid_annotation_target, unnecessary_question_mark

part of 'error.dart';

// **************************************************************************
// FreezedGenerator
// **************************************************************************

// dart format off
T _$identity<T>(T value) => value;
/// @nodoc
mixin _$MobileError {

 String get code; String get message; bool get retryable;
/// Create a copy of MobileError
/// with the given fields replaced by the non-null parameter values.
@JsonKey(includeFromJson: false, includeToJson: false)
@pragma('vm:prefer-inline')
$MobileErrorCopyWith<MobileError> get copyWith => _$MobileErrorCopyWithImpl<MobileError>(this as MobileError, _$identity);



@override
bool operator ==(Object other) {
  return identical(this, other) || (other.runtimeType == runtimeType&&other is MobileError&&(identical(other.code, code) || other.code == code)&&(identical(other.message, message) || other.message == message)&&(identical(other.retryable, retryable) || other.retryable == retryable));
}


@override
int get hashCode => Object.hash(runtimeType,code,message,retryable);

@override
String toString() {
  return 'MobileError(code: $code, message: $message, retryable: $retryable)';
}


}

/// @nodoc
abstract mixin class $MobileErrorCopyWith<$Res>  {
  factory $MobileErrorCopyWith(MobileError value, $Res Function(MobileError) _then) = _$MobileErrorCopyWithImpl;
@useResult
$Res call({
 String code, String message, bool retryable
});




}
/// @nodoc
class _$MobileErrorCopyWithImpl<$Res>
    implements $MobileErrorCopyWith<$Res> {
  _$MobileErrorCopyWithImpl(this._self, this._then);

  final MobileError _self;
  final $Res Function(MobileError) _then;

/// Create a copy of MobileError
/// with the given fields replaced by the non-null parameter values.
@pragma('vm:prefer-inline') @override $Res call({Object? code = null,Object? message = null,Object? retryable = null,}) {
  return _then(_self.copyWith(
code: null == code ? _self.code : code // ignore: cast_nullable_to_non_nullable
as String,message: null == message ? _self.message : message // ignore: cast_nullable_to_non_nullable
as String,retryable: null == retryable ? _self.retryable : retryable // ignore: cast_nullable_to_non_nullable
as bool,
  ));
}

}


/// Adds pattern-matching-related methods to [MobileError].
extension MobileErrorPatterns on MobileError {
/// A variant of `map` that fallback to returning `orElse`.
///
/// It is equivalent to doing:
/// ```dart
/// switch (sealedClass) {
///   case final Subclass value:
///     return ...;
///   case _:
///     return orElse();
/// }
/// ```

@optionalTypeArgs TResult maybeMap<TResult extends Object?>({TResult Function( MobileError_Failure value)?  failure,required TResult orElse(),}){
final _that = this;
switch (_that) {
case MobileError_Failure() when failure != null:
return failure(_that);case _:
  return orElse();

}
}
/// A `switch`-like method, using callbacks.
///
/// Callbacks receives the raw object, upcasted.
/// It is equivalent to doing:
/// ```dart
/// switch (sealedClass) {
///   case final Subclass value:
///     return ...;
///   case final Subclass2 value:
///     return ...;
/// }
/// ```

@optionalTypeArgs TResult map<TResult extends Object?>({required TResult Function( MobileError_Failure value)  failure,}){
final _that = this;
switch (_that) {
case MobileError_Failure():
return failure(_that);}
}
/// A variant of `map` that fallback to returning `null`.
///
/// It is equivalent to doing:
/// ```dart
/// switch (sealedClass) {
///   case final Subclass value:
///     return ...;
///   case _:
///     return null;
/// }
/// ```

@optionalTypeArgs TResult? mapOrNull<TResult extends Object?>({TResult? Function( MobileError_Failure value)?  failure,}){
final _that = this;
switch (_that) {
case MobileError_Failure() when failure != null:
return failure(_that);case _:
  return null;

}
}
/// A variant of `when` that fallback to an `orElse` callback.
///
/// It is equivalent to doing:
/// ```dart
/// switch (sealedClass) {
///   case Subclass(:final field):
///     return ...;
///   case _:
///     return orElse();
/// }
/// ```

@optionalTypeArgs TResult maybeWhen<TResult extends Object?>({TResult Function( String code,  String message,  bool retryable)?  failure,required TResult orElse(),}) {final _that = this;
switch (_that) {
case MobileError_Failure() when failure != null:
return failure(_that.code,_that.message,_that.retryable);case _:
  return orElse();

}
}
/// A `switch`-like method, using callbacks.
///
/// As opposed to `map`, this offers destructuring.
/// It is equivalent to doing:
/// ```dart
/// switch (sealedClass) {
///   case Subclass(:final field):
///     return ...;
///   case Subclass2(:final field2):
///     return ...;
/// }
/// ```

@optionalTypeArgs TResult when<TResult extends Object?>({required TResult Function( String code,  String message,  bool retryable)  failure,}) {final _that = this;
switch (_that) {
case MobileError_Failure():
return failure(_that.code,_that.message,_that.retryable);}
}
/// A variant of `when` that fallback to returning `null`
///
/// It is equivalent to doing:
/// ```dart
/// switch (sealedClass) {
///   case Subclass(:final field):
///     return ...;
///   case _:
///     return null;
/// }
/// ```

@optionalTypeArgs TResult? whenOrNull<TResult extends Object?>({TResult? Function( String code,  String message,  bool retryable)?  failure,}) {final _that = this;
switch (_that) {
case MobileError_Failure() when failure != null:
return failure(_that.code,_that.message,_that.retryable);case _:
  return null;

}
}

}

/// @nodoc


class MobileError_Failure extends MobileError {
  const MobileError_Failure({required this.code, required this.message, required this.retryable}): super._();


@override final  String code;
@override final  String message;
@override final  bool retryable;

/// Create a copy of MobileError
/// with the given fields replaced by the non-null parameter values.
@override @JsonKey(includeFromJson: false, includeToJson: false)
@pragma('vm:prefer-inline')
$MobileError_FailureCopyWith<MobileError_Failure> get copyWith => _$MobileError_FailureCopyWithImpl<MobileError_Failure>(this, _$identity);



@override
bool operator ==(Object other) {
  return identical(this, other) || (other.runtimeType == runtimeType&&other is MobileError_Failure&&(identical(other.code, code) || other.code == code)&&(identical(other.message, message) || other.message == message)&&(identical(other.retryable, retryable) || other.retryable == retryable));
}


@override
int get hashCode => Object.hash(runtimeType,code,message,retryable);

@override
String toString() {
  return 'MobileError.failure(code: $code, message: $message, retryable: $retryable)';
}


}

/// @nodoc
abstract mixin class $MobileError_FailureCopyWith<$Res> implements $MobileErrorCopyWith<$Res> {
  factory $MobileError_FailureCopyWith(MobileError_Failure value, $Res Function(MobileError_Failure) _then) = _$MobileError_FailureCopyWithImpl;
@override @useResult
$Res call({
 String code, String message, bool retryable
});




}
/// @nodoc
class _$MobileError_FailureCopyWithImpl<$Res>
    implements $MobileError_FailureCopyWith<$Res> {
  _$MobileError_FailureCopyWithImpl(this._self, this._then);

  final MobileError_Failure _self;
  final $Res Function(MobileError_Failure) _then;

/// Create a copy of MobileError
/// with the given fields replaced by the non-null parameter values.
@override @pragma('vm:prefer-inline') $Res call({Object? code = null,Object? message = null,Object? retryable = null,}) {
  return _then(MobileError_Failure(
code: null == code ? _self.code : code // ignore: cast_nullable_to_non_nullable
as String,message: null == message ? _self.message : message // ignore: cast_nullable_to_non_nullable
as String,retryable: null == retryable ? _self.retryable : retryable // ignore: cast_nullable_to_non_nullable
as bool,
  ));
}


}

// dart format on
